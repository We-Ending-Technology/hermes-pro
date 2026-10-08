from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

KEYWORDS = {
    "python": 18, "api": 16, "automation": 16, "automação": 16,
    "ai": 14, "ia": 14, "data": 12, "scraping": 10, "backend": 10,
    "fastapi": 10, "django": 8, "integration": 12, "integração": 12,
    "pandas": 8, "website": 12, "site": 12, "seo": 10, "landing page": 10,
}
BLOCKED = ("captcha bypass", "credential theft", "malware", "spam bot", "fraud", "phishing", "cracking")


@dataclass
class Opportunity:
    title: str
    url: str
    source: str
    summary: str = ""
    score: int = 0
    difficulty: str = "unknown"
    suggested_price: float | None = None
    proposal: str = ""
    rejection_reason: str | None = None
    opportunity_type: str = "service"
    signals: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class _Parser(HTMLParser):
    def __init__(self, base: str):
        super().__init__()
        self.base = base
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.text: list[str] = []
        self.title = ""

    def handle_starttag(self, tag, attrs):
        attrs_map = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = attrs_map.get("href")
            if href:
                self.href = urljoin(self.base, href)
                self.text = []

    def handle_data(self, data):
        if getattr(self, "_in_title", False):
            self.title += data
        if self.href:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "a" and self.href:
            text = re.sub(r"\s+", " ", " ".join(self.text)).strip()
            if text:
                self.links.append((self.href, text[:300]))
            self.href = None
            self.text = []


class OpportunityHunter:
    """Controls recurring acquisition cycles and prevents rediscovery of the same work."""
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    async def _seen_keys(self) -> set[str]:
        try:
            rows = await self.db.select("hermes_opportunities", params={"select":"idempotency_key", "limit":"5000"})
            return {r.get("idempotency_key") for r in (rows or []) if r.get("idempotency_key")}
        except Exception:
            return set()

    def rank(self, items: list[Opportunity]) -> list[Opportunity]:
        # Expected-return heuristic: value x fit x confidence, penalized by difficulty.
        for item in items:
            price = item.suggested_price or 0
            difficulty_penalty = {"baixa": 1.0, "média": .82, "alta": .62, "unknown": .70}.get(item.difficulty, .70)
            recurring = 1.15 if item.opportunity_type in {"local_service", "affiliate"} else 1.0
            item.metadata["expected_return"] = round(price * (item.score / 100) * difficulty_penalty * recurring, 2)
        return sorted(items, key=lambda x: (x.metadata.get("expected_return", 0), x.score), reverse=True)

    async def cycle(self, limit: int = 1000):
        engine = OpportunityEngine(self.db, self.settings)
        result = await engine.run(limit)
        ranked = self.rank([Opportunity(**{k:v for k,v in x.items() if k in Opportunity.__dataclass_fields__}) for x in result.get("top", [])])
        return {
            **result,
            "hunter": {
                "new": result.get("new", len(ranked)),
                "duplicates_skipped": result.get("duplicates_skipped", 0),
                "ranking": [x.__dict__ for x in ranked[:50]],
                "policy": "expected_return",
            },
        }


class OpportunityEngine:
    """Multi-channel acquisition radar.

    Channels are deliberately optional. The engine works with the existing public
    job sources without extra credentials, while Google Places, affiliate directories
    and custom discovery sources activate only when configured.
    """

    def __init__(self, db, settings):
        self.db = db
        self.settings = settings
        self.http_headers = {"User-Agent": "Hermes-Pro-Radar/2.0"}

    def _csv(self, name: str) -> list[str]:
        return [x.strip() for x in os.getenv(name, "").split(",") if x.strip()]

    def source_urls(self) -> list[str]:
        configured = [x.strip() for x in self.settings.radar_source_urls.split(",") if x.strip()]
        return configured or [
            "https://www.freelancer.com/jobs/python",
            "https://www.99freelas.com.br/projects?q=python",
            "https://www.workana.com/pt/jobs?skills=python",
            "https://www.workana.com/pt/jobs?skills=api",
        ]

    async def collect_jobs(self, limit: int = 1000) -> list[Opportunity]:
        results: dict[str, Opportunity] = {}
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=self.http_headers) as client:
            for source in self.source_urls() + self._csv("RADAR_DISCOVERY_URLS"):
                for page in range(1, 11):
                    url = source if page == 1 else source + ("&" if "?" in source else "?") + f"page={page}"
                    try:
                        response = await client.get(url)
                        response.raise_for_status()
                    except Exception:
                        break
                    parser = _Parser(str(response.url))
                    parser.feed(response.text)
                    found = 0
                    for href, title in parser.links:
                        if not any(k in title.lower() for k in KEYWORDS):
                            continue
                        key = self.canonical(href)
                        if key not in results:
                            results[key] = Opportunity(
                                title=title,
                                url=key,
                                source=urlparse(key).netloc,
                                opportunity_type="service",
                                metadata={"channel": "internet_jobs", "discovered_from": source},
                            )
                            found += 1
                        if len(results) >= limit:
                            return list(results.values())
                    if not found:
                        break
        return list(results.values())

    async def collect_google_places(self, limit: int = 100) -> list[Opportunity]:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
        if not api_key:
            return []

        queries = self._csv("RADAR_LOCAL_QUERIES") or [
            "empresas", "restaurantes", "oficinas", "clínicas", "dentistas",
            "academias", "salões", "barbearias", "oficinas", "lojas",
            "imobiliárias", "contadores", "advogados", "hotéis", "pousadas",
        ]
        city = os.getenv("RADAR_LOCAL_CITY", "Arcos, MG, Brasil")
        results: dict[str, Opportunity] = {}
        headers = {**self.http_headers, "X-Goog-Api-Key": api_key,
                   "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.websiteUri,places.googleMapsUri,places.businessStatus,places.rating,places.userRatingCount"}

        async with httpx.AsyncClient(timeout=25, headers=headers) as client:
            for query in queries:
                try:
                    response = await client.post(
                        "https://places.googleapis.com/v1/places:searchText",
                        json={"textQuery": f"{query} em {city}", "pageSize": min(20, limit)},
                    )
                    response.raise_for_status()
                    places = response.json().get("places", [])
                except Exception:
                    continue

                for place in places:
                    place_id = place.get("id")
                    if not place_id or place_id in results:
                        continue
                    name = (place.get("displayName") or {}).get("text", "Negócio local")
                    website = place.get("websiteUri")
                    maps_url = place.get("googleMapsUri", "")
                    signals = {
                        "website_missing": not bool(website),
                        "rating": place.get("rating"),
                        "review_count": place.get("userRatingCount"),
                        "business_status": place.get("businessStatus"),
                    }
                    summary = f"{name} — {place.get('formattedAddress', city)}."
                    if not website:
                        summary += " Não foi encontrado website no dado retornado pelo Places."
                    results[place_id] = Opportunity(
                        title=f"Oportunidade digital: {name}",
                        url=website or maps_url or f"https://www.google.com/maps/search/?api=1&query={name}",
                        source="google_maps",
                        summary=summary,
                        opportunity_type="local_service",
                        signals=signals,
                        metadata={"place_id": place_id, "city": city, "website": website, "maps_url": maps_url},
                    )
                    if len(results) >= limit:
                        return list(results.values())
        return list(results.values())

    async def audit_local_websites(self, items: list[Opportunity]) -> None:
        candidates = [x for x in items if x.opportunity_type == "local_service" and x.metadata.get("website")]
        if not candidates:
            return
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=self.http_headers) as client:
            for item in candidates:
                url = item.metadata["website"]
                try:
                    response = await client.get(url)
                    html = response.text[:1_000_000]
                    lower = html.lower()
                    parser = _Parser(str(response.url))
                    parser.feed(html)
                    issues = []
                    if response.status_code >= 400:
                        issues.append("site retorna erro HTTP")
                    if '<meta name="viewport"' not in lower and "name='viewport'" not in lower:
                        issues.append("sem viewport responsivo detectável")
                    if "<title" not in lower or not parser.title.strip():
                        issues.append("sem título HTML detectável")
                    if "https://" not in url.lower():
                        issues.append("URL original não usa HTTPS")
                    if len(html) < 5000:
                        issues.append("conteúdo muito pequeno")
                    item.signals.update({
                        "http_status": response.status_code,
                        "final_url": str(response.url),
                        "website_issues": issues,
                    })
                    item.summary += " Auditoria: " + (", ".join(issues) if issues else "nenhum problema básico detectado.")
                    if issues:
                        item.score += min(30, len(issues) * 8)
                        item.metadata["recommended_service"] = "site/landing page + manutenção/SEO"
                except Exception as exc:
                    item.signals["audit_error"] = type(exc).__name__
                    item.summary += " Não foi possível auditar o site agora."

    async def collect_affiliates(self, limit: int = 100) -> list[Opportunity]:
        urls = self._csv("RADAR_AFFILIATE_URLS")
        if not urls:
            return []
        results: dict[str, Opportunity] = {}
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=self.http_headers) as client:
            for source in urls:
                try:
                    response = await client.get(source)
                    response.raise_for_status()
                except Exception:
                    continue
                parser = _Parser(str(response.url))
                parser.feed(response.text)
                for href, title in parser.links:
                    text = title.lower()
                    if not any(k in text for k in ("affiliate", "afiliado", "partner", "program", "comissão", "commission", "referral")):
                        continue
                    key = self.canonical(href)
                    if key in results:
                        continue
                    results[key] = Opportunity(
                        title=f"Programa de afiliados: {title}",
                        url=key,
                        source=urlparse(key).netloc,
                        opportunity_type="affiliate",
                        summary="Programa encontrado em fonte configurada pelo usuário; requisitos e comissão devem ser validados antes da divulgação.",
                        signals={"affiliate_signal": True},
                        metadata={"discovered_from": source},
                    )
                    if len(results) >= limit:
                        return list(results.values())
        return list(results.values())

    def score(self, item: Opportunity) -> Opportunity:
        text = (item.title + " " + item.summary).lower()
        if any(b in text for b in BLOCKED):
            item.rejection_reason = "conteúdo incompatível"
            return item

        if item.opportunity_type == "local_service":
            base = 45
            if item.signals.get("website_missing"):
                base += 30
                item.metadata["recommended_service"] = "criação de site + presença digital"
            if item.signals.get("website_issues"):
                base += min(20, len(item.signals["website_issues"]) * 5)
            if (item.signals.get("review_count") or 0) >= 20:
                base += 5
            item.score = min(100, base)
            item.difficulty = "baixa" if item.score >= 75 else "média"
            item.suggested_price = 1200 if item.signals.get("website_missing") else 700
            item.proposal = (
                f"Olá! Analisei a presença digital de {item.title.replace('Oportunidade digital: ', '')}. "
                "Posso criar/modernizar o site e organizar uma presença digital profissional, "
                f"com orçamento inicial de R$ {item.suggested_price:.0f}, ajustável após os requisitos."
            )
            return item

        if item.opportunity_type == "affiliate":
            item.score = 55
            item.difficulty = "média"
            item.suggested_price = 0
            item.proposal = "Avaliar programa, regras, comissão e demanda antes de promover."
            return item

        match = sum(weight for keyword, weight in KEYWORDS.items() if keyword in text)
        item.score = min(100, match + 18 + (15 if len(text) < 700 else 8))
        item.difficulty = "baixa" if item.score >= 65 else ("média" if item.score >= 45 else "alta")
        item.suggested_price = 450 if item.score >= 80 else (300 if item.score >= 65 else (200 if item.score >= 50 else 120))
        item.proposal = (
            f"Olá! Vi o projeto “{item.title}” e consigo atacar o problema com Python, APIs e automação. "
            f"Posso estruturar, implementar, testar e documentar a solução. Estimativa inicial: "
            f"R$ {item.suggested_price:.0f}, ajustável após confirmar requisitos e acessos."
        )
        if item.score < 40:
            item.rejection_reason = "aderência insuficiente"
        return item

    @staticmethod
    def canonical(url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")

    async def run(self, limit: int = 1000):
        jobs, locals_, affiliates = await self.collect_jobs(limit), await self.collect_google_places(min(limit, 100)), await self.collect_affiliates(min(limit, 100))
        await self.audit_local_websites(locals_)
        items = jobs + locals_ + affiliates
        items = [self.score(x) for x in items]
        minimum = max(0, min(100, self.settings.radar_min_score))
        top = sorted([x for x in items if not x.rejection_reason and x.score >= minimum], key=lambda x: x.score, reverse=True)[:50]
        now = datetime.now(timezone.utc).isoformat()
        persisted = 0
        try:
            existing_rows = await self.db.select("hermes_opportunities", params={"select":"idempotency_key", "limit":"5000"})
            existing_keys = {r.get("idempotency_key") for r in (existing_rows or []) if r.get("idempotency_key")}
        except Exception:
            existing_keys = set()

        fresh = []
        for item in top:
            key = item.opportunity_type + ":" + self.canonical(item.url)
            if key not in existing_keys:
                fresh.append(item)

        for item in fresh:
            try:
                await self.db.insert("hermes_opportunities", {
                    "type": item.opportunity_type,
                    "source": item.source,
                    "source_url": item.url,
                    "title": item.title,
                    "description": item.summary,
                    "url": item.url,
                    "summary": item.summary,
                    "signals": item.signals,
                    "score": item.score,
                    "confidence": 85 if item.opportunity_type != "affiliate" else 70,
                    "difficulty": item.difficulty,
                    "suggested_price": item.suggested_price,
                    "currency": "BRL",
                    "proposal": item.proposal,
                    "status": "approved",
                    "application_status": "not_attempted",
                    "idempotency_key": item.opportunity_type + ":" + self.canonical(item.url),
                    "metadata": {"radar": "autonomous", **item.metadata},
                    "created_at": now,
                    "updated_at": now,
                })
                persisted += 1
            except Exception:
                pass

        return {
            "collected": len(items),
            "approved": len(top),
            "new": len(fresh),
            "duplicates_skipped": max(0, len(top) - len(fresh)),
            "persisted": persisted,
            "channels": {
                "internet_jobs": len(jobs),
                "local_business": len(locals_),
                "affiliate": len(affiliates),
            },
            "top": [x.__dict__ for x in top],
            "ran_at": now,
        }
