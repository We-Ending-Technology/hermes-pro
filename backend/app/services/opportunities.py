from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

KEYWORDS = {
    "python": 18, "api": 16, "automation": 16, "automação": 16, "ai": 14,
    "ia": 14, "data": 12, "scraping": 10, "backend": 10, "fastapi": 10,
    "django": 8, "integration": 12, "integração": 12, "pandas": 8,
}
BLOCKED = ("captcha bypass", "credential theft", "malware", "spam bot", "fraud", "phishing", "cracking")


@dataclass
class Opportunity:
    title: str
    url: str
    source: str
    summary: str = ""
    budget: float | None = None
    currency: str = "BRL"
    score: int = 0
    difficulty: str = "unknown"
    suggested_price: float | None = None
    proposal: str = ""
    rejection_reason: str | None = None


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href = urljoin(self.base_url, href)
                self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            text = re.sub(r"\s+", " ", " ".join(self._text)).strip()
            if text:
                self.links.append((self._href, text[:300]))
            self._href = None
            self._text = []


class OpportunityEngine:
    def __init__(self, db, settings):
        self.db = db
        self.settings = settings

    def source_urls(self) -> list[str]:
        configured = [x.strip() for x in self.settings.radar_source_urls.split(",") if x.strip()]
        return configured or [
            "https://www.freelancer.com/jobs/python",
            "https://www.99freelas.com.br/projects?q=python",
            "https://www.workana.com/pt/jobs?skills=python",
            "https://www.workana.com/pt/jobs?skills=api",
        ]

    async def collect(self, limit: int = 1000) -> list[Opportunity]:
        results: dict[str, Opportunity] = {}
        headers = {"User-Agent": "Hermes-Pro-Radar/1.0 (+authorized-public-discovery)"}
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=headers) as client:
            for source_url in self.source_urls():
                for page in range(1, 11):
                    url = source_url if page == 1 else self._page_url(source_url, page)
                    try:
                        response = await client.get(url)
                        response.raise_for_status()
                    except Exception:
                        break
                    parser = _LinkParser(str(response.url))
                    parser.feed(response.text)
                    found = 0
                    for href, title in parser.links:
                        if not self._candidate_link(href, title):
                            continue
                        key = self._canonical(href)
                        if key not in results:
                            source = urlparse(href).netloc
                            results[key] = Opportunity(title=title, url=href, source=source)
                            found += 1
                        if len(results) >= limit:
                            return list(results.values())
                    if found == 0:
                        break
        return list(results.values())

    def score(self, item: Opportunity) -> Opportunity:
        text = (item.title + " " + item.summary).lower()
        if any(x in text for x in BLOCKED):
            item.rejection_reason = "conteúdo incompatível com as regras de execução"
            return item
        match = sum(weight for word, weight in KEYWORDS.items() if word in text)
        recency = 20 if any(x in text for x in ("hoje", "today", "agora")) else 10
        simplicity = 18 if len(text) < 700 else 8
        autonomy = 15 if not any(x in text for x in ("certificado digital", "hardware", "android nativo", "iOS nativo")) else 3
        item.score = min(100, match + recency + simplicity + autonomy)
        item.difficulty = "baixa" if item.score >= 65 else ("média" if item.score >= 45 else "alta")
        item.suggested_price = self._price(item.score)
        item.proposal = self._proposal(item)
        if item.score < 40:
            item.rejection_reason = "aderência insuficiente"
        return item

    def _candidate_link(self, href: str, title: str) -> bool:
        text = title.lower()
        return bool(title.strip()) and any(k in text for k in KEYWORDS) and href.startswith(("http://", "https://"))

    @staticmethod
    def _canonical(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    @staticmethod
    def _page_url(url: str, page: int) -> str:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}page={page}"

    @staticmethod
    def _price(score: int) -> float:
        if score >= 80: return 450.0
        if score >= 65: return 300.0
        if score >= 50: return 200.0
        return 120.0

    @staticmethod
    def _proposal(item: Opportunity) -> str:
        return (
            f"Olá! Vi o projeto “{item.title}” e consigo atacar o problema com Python, "
            "integrações/API e automação de forma objetiva. Posso estruturar a solução, "
            "implementar o fluxo, tratar erros e entregar código organizado + instruções de uso. "
            f"Para o escopo visível, minha estimativa inicial é R$ {item.suggested_price:.0f}, "
            "ajustável após confirmar os requisitos e os acessos necessários. "
            "Não incluo no orçamento qualquer credencial ou serviço externo que o cliente não forneça."
        )

    async def run(self, limit: int = 1000, persist: bool = True) -> dict:
        candidates = await self.collect(limit)
        scored = [self.score(x) for x in candidates]
        approved = [x for x in scored if not x.rejection_reason]
        approved.sort(key=lambda x: x.score, reverse=True)
        top = approved[:10]
        if persist and hasattr(self.db, "insert"):
            now = datetime.now(timezone.utc).isoformat()
            for item in top:
                await self.db.insert("hermes_opportunities", {
                    "source": item.source, "title": item.title, "url": item.url,
                    "summary": item.summary, "score": item.score,
                    "difficulty": item.difficulty, "suggested_price": item.suggested_price,
                    "currency": item.currency, "proposal": item.proposal,
                    "status": "approved", "created_at": now, "updated_at": now,
                })
        return {
            "collected": len(candidates),
            "approved": len(approved),
            "top": [item.__dict__ for item in top],
            "ran_at": datetime.now(timezone.utc).isoformat(),
        }
