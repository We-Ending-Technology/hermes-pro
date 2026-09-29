from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.config import get_settings
from ..integrations.freelancer import build_freelancer_adapter


@dataclass(frozen=True)
class Opportunity:
    source: str
    external_id: str
    title: str
    url: str
    description: str
    tags: list[str]
    budget: float | None
    currency: str
    discovery_automation_allowed: bool
    raw: dict[str, Any]

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(f"{self.source}:{self.external_id}".encode()).hexdigest()[:32]


SOURCES = {
    "remoteok": {
        "kind": "public_api",
        "url": "https://remoteok.com/api",
        "automation_allowed": True,
    },
    "remotive": {
        "kind": "public_api",
        "url": "https://remotive.com/api/remote-jobs",
        "automation_allowed": True,
    },
    "arbeitnow": {
        "kind": "public_api",
        "url": "https://www.arbeitnow.com/api/job-board-api",
        "automation_allowed": True,
    },
    "workana": {
        "kind": "manual_or_official_api_only",
        "url": "https://www.workana.com/",
        "automation_allowed": False,
    },
    "99freelas": {
        "kind": "manual_or_official_api_only",
        "url": "https://www.99freelas.com.br/",
        "automation_allowed": False,
    },
    "freelancer": {
        "kind": "official_api",
        "url": "https://developer.freelancer.com/",
        "automation_allowed": True,
    },
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _money(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _match(title: str, description: str, tags: list[str]) -> bool:
    haystack = " ".join([title, description, *tags]).lower()
    keywords = (
        "python", "fastapi", "api", "automation", "automação", "ai", "artificial intelligence",
        "data", "bug", "testing", "report", "dashboard", "scraping", "integration",
        "backend", "software", "developer", "machine learning",
    )
    return any(k in haystack for k in keywords)


async def fetch_opportunities(limit: int = 40) -> list[Opportunity]:
    results: list[Opportunity] = []
    headers = {"User-Agent": "Hermes-Pro/1.0 opportunity-radar"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0), headers=headers, follow_redirects=True) as client:
        for source, cfg in SOURCES.items():
            if cfg["kind"] != "public_api":
                continue
            try:
                response = await client.get(cfg["url"])
                response.raise_for_status()
                data = response.json()
            except Exception:
                continue

            rows = data.get("jobs", data) if isinstance(data, dict) else data
            if not isinstance(rows, list):
                continue
            for row in rows[:limit]:
                if not isinstance(row, dict):
                    continue
                title = _text(row.get("position") or row.get("title") or row.get("name"))
                description = _text(row.get("description") or row.get("snippet"))
                tags = [str(x) for x in (row.get("tags") or row.get("skills") or []) if x]
                external_id = _text(row.get("id") or row.get("slug") or row.get("url") or title)
                url = _text(row.get("url") or row.get("job_url") or row.get("apply_url"))
                if not title or not url or not _match(title, description, tags):
                    continue
                results.append(Opportunity(
                    source=source,
                    external_id=external_id,
                    title=title,
                    url=url,
                    description=description[:6000],
                    tags=tags[:30],
                    budget=_money(row.get("salary") or row.get("salary_min")),
                    currency=_text(row.get("currency") or "USD") or "USD",
                    discovery_automation_allowed=bool(cfg["automation_allowed"]),
                    raw=row,
                ))
    return results


def score_opportunity(item: Opportunity) -> dict[str, Any]:
    text = f"{item.title} {item.description} {' '.join(item.tags)}".lower()
    skills = {
        "python": "python" in text,
        "api": "api" in text or "integration" in text,
        "automation": "automation" in text or "automação" in text,
        "ai": " ai " in f" {text} " or "artificial intelligence" in text,
        "data": "data" in text,
        "testing": "test" in text or "bug" in text,
    }
    fit = min(100, 35 + sum(10 for v in skills.values() if v))
    urgency = 70 if any(x in text for x in ("urgent", "asap", "immediately", "urgente")) else 45
    value = 55 if item.budget is None else min(100, 40 + int(min(item.budget, 6000) / 60))
    score = round(fit * 0.55 + urgency * 0.15 + value * 0.30)
    return {
        "score": score,
        "fit": fit,
        "urgency": urgency,
        "value": value,
        "skills": skills,
        "discovery_automation_allowed": item.discovery_automation_allowed,                    "application_automation_allowed": False,
        "source_policy": "automated_public_api" if item.discovery_automation_allowed else "manual_only",
    }
