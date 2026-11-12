from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx

GOOGLE_TRENDS_BR_RSS = "https://trends.google.com/trending/rss?geo=BR"
HT_NS = {"ht": "https://trends.google.com/trending/rss"}
STOPWORDS = {"para", "com", "sem", "sobre", "como", "guia", "curso", "ebook", "livro", "de", "da", "do", "das", "dos", "e", "a", "o", "em", "por"}


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9áàâãéêíóôõúç]+", value.casefold())
        if len(token) > 2 and token not in STOPWORDS
    }


def _traffic_floor(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d[\d,.]*)", value.replace(",", ""))
    if not match:
        return None
    try:
        return int(float(match.group(1)))
    except ValueError:
        return None


async def fetch_google_trends_br(niche: str) -> dict[str, Any]:
    """Match a niche only against Google's public Brazil Trending RSS; this is not keyword history."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=True) as client:
        response = await client.get(GOOGLE_TRENDS_BR_RSS, headers={"User-Agent": "HermesProRadar/1.0"})
        response.raise_for_status()
    root = ET.fromstring(response.content)
    query_tokens = _tokens(niche)
    matches = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        trend_tokens = _tokens(title)
        overlap = len(query_tokens & trend_tokens)
        ratio = overlap / max(1, len(query_tokens))
        if query_tokens and (niche.casefold() in title.casefold() or (overlap >= 1 and ratio >= 0.5)):
            traffic = item.findtext("ht:approx_traffic", namespaces=HT_NS)
            matches.append({
                "title": title,
                "approx_traffic": traffic,
                "demand_estimated_floor": _traffic_floor(traffic),
                "published_at": item.findtext("pubDate"),
                "source_url": GOOGLE_TRENDS_BR_RSS,
            })
    return {
        "source": "Google Trends Brasil — Trending RSS",
        "source_url": GOOGLE_TRENDS_BR_RSS,
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "matches": matches,
        "demand_exists": bool(matches),
        "competition": None,
        "limitations": [
            "O RSS contém apenas tendências recentes do Brasil, não volume histórico de palavras-chave.",
            "O tráfego é uma faixa aproximada fornecida pelo Google, não uma contagem exata.",
            "Concorrência não é medida por esta fonte e permanece desconhecida.",
        ],
    }


async def validate_and_record_niche(store, niche: str) -> dict[str, Any]:
    result = await fetch_google_trends_br(niche)
    evidence = result["matches"]
    demand_floor = max(
        (item["demand_estimated_floor"] for item in evidence if item["demand_estimated_floor"] is not None),
        default=None,
    )
    await store.db.insert("hermes_market_signals", {
        "niche": niche.strip(),
        "source": result["source"],
        "source_url": result["source_url"],
        "demand_estimated": demand_floor,
        "competition": None,
        "evidence": {"matches": evidence, "limitations": result["limitations"]},
        "data_consulted": result["queried_at"],
        "positive": result["demand_exists"],
    })
    return result
