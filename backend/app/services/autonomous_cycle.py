from __future__ import annotations

import hashlib
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from .commerce_store import CommerceStore
from .opportunities import OpportunityEngine, OpportunityInput
from ..core.config import get_settings

TOPICS = (
    "educação",
    "produtividade",
    "carreira",
    "tecnologia",
    "organização financeira",
    "documentos e currículo",
    "pequenos negócios",
)

_opportunity_engine = OpportunityEngine()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


async def _rss(url: str) -> ET.Element:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return ET.fromstring(response.content)


async def _create_signal(store: CommerceStore, title: str, link: str, source: str, metadata: dict[str, Any]):
    title = _clean(title)
    if not title:
        return None
    key = hashlib.sha256(f"{source}:{title}:{link}".encode()).hexdigest()[:32]
    scored = _opportunity_engine.score(OpportunityInput())
    try:
        return await store.create_opportunity(
            {
                "type": "product",
                "title": f"Sinal de oportunidade: {title}",
                "description": "Sinal público para validação posterior; não é confirmação de demanda.",
                "source": source,
                "source_url": link,
                "signals": {"public_signal": 1.0},
                "score": scored.score,
                "confidence": scored.confidence,
                "status": "discovered",
                "metadata": metadata,
            },
            idempotency_key=key,
        )
    except Exception:
        return None


async def discover_google_trends(store: CommerceStore, geo: str = "BR", limit: int = 20):
    if not get_settings().trends_enabled:
        return []
    url = f"https://trends.google.com/trending/rss?geo={urllib.parse.quote(geo)}"
    try:
        root = await _rss(url)
    except Exception:
        return []
    found = []
    for item in root.findall(".//item")[:limit]:
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        row = await _create_signal(store, title, link, "google_trends_public_rss", {"geo": geo, "kind": "trending_now"})
        if row:
            found.append(row)
    return found


async def discover_google_news(store: CommerceStore, limit: int = 12):
    found = []
    per_topic = max(1, limit // len(TOPICS))
    for topic in TOPICS:
        params = urllib.parse.urlencode({"q": topic, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})
        try:
            root = await _rss(f"https://news.google.com/rss/search?{params}")
        except Exception:
            continue
        for item in root.findall("./channel/item")[:per_topic]:
            row = await _create_signal(
                store,
                item.findtext("title") or "",
                item.findtext("link") or "",
                "google_news_rss",
                {"topic": topic, "kind": "news_signal"},
            )
            if row:
                found.append(row)
    return found


async def discover_public_signals(store: CommerceStore, limit: int = 24):
    trends = await discover_google_trends(store, geo=get_settings().trends_geo, limit=min(20, limit))
    news = await discover_google_news(store, limit=max(4, limit - len(trends)))
    return trends + news
