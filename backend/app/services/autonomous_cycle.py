from __future__ import annotations

import hashlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from ..commerce.opportunities import score_opportunity
from .commerce_store import CommerceStore


TOPICS = (
    "educação",
    "produtividade",
    "carreira",
    "tecnologia",
    "organização financeira",
    "documentos e currículo",
    "pequenos negócios",
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


async def discover_public_signals(store: CommerceStore, limit: int = 8) -> list[dict[str, Any]]:
    """Collects public Google News RSS headlines as market signals.

    This is intentionally a signal source, not proof of demand. Missing metrics remain missing.
    """
    created: list[dict[str, Any]] = []
    for topic in TOPICS:
        query = urllib.parse.quote(topic)
        url = f"https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                raw = response.read()
            root = ET.fromstring(raw)
        except Exception:
            continue
        for item in root.findall("./channel/item")[: max(1, limit // len(TOPICS))]:
            title = _clean(item.findtext("title") or "")
            link = item.findtext("link") or ""
            if not title:
                continue
            key = hashlib.sha256(f"news:{title}:{link}".encode()).hexdigest()[:32]
            signals = {"public_news_signal": 1.0, "topic": topic}
            scored = score_opportunity(
                demand=1.0,
                margin=None,
                ease=0.7,
                conversion=None,
                capacity=0.8,
                competition=None,
                cost=0.9,
                risk=0.9,
            )
            try:
                row = await store.create_opportunity(
                    {
                        "type": "product",
                        "title": f"Sinal de oportunidade: {title}",
                        "description": "Sinal público para pesquisa posterior; não é confirmação de demanda.",
                        "source": "google_news_rss",
                        "source_url": link,
                        "signals": signals,
                        "score": scored.score,
                        "confidence": scored.confidence,
                        "status": "discovered",
                        "metadata": {"topic": topic, "requires_validation": True},
                    },
                    idempotency_key=key,
                )
                created.append(row)
            except Exception:
                continue
    return created
