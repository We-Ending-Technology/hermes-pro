from __future__ import annotations

import re
from typing import Any


def build_commercial_metadata(
    *,
    strategy: dict[str, Any],
    description: str,
    short_description: str,
    keywords: list[str],
    suggested_price: float,
    price_rationale: str,
) -> dict[str, Any]:
    price = round(float(suggested_price), 2)
    if price <= 0:
        raise ValueError("suggested_price must be positive")
    return {
        "title": str(strategy.get("title") or "").strip(),
        "subtitle": str(strategy.get("subtitle") or "").strip(),
        "description": description.strip(),
        "short_description": short_description.strip(),
        "audience": str(strategy.get("audience") or "").strip(),
        "category": str(strategy.get("category") or "").strip(),
        "keywords": [str(item).strip() for item in keywords if str(item).strip()],
        "suggested_price": price,
        "price_rationale": price_rationale.strip(),
        "price_basis": "recommendation",
        "publication_status": "not_published",
        "publication_ready": False,
    }


def mark_publication_ready(metadata: dict[str, Any]) -> dict[str, Any]:
    result = dict(metadata)
    required = (
        result.get("title"), result.get("description"), result.get("audience"),
        result.get("category"), result.get("keywords"), result.get("suggested_price"),
        result.get("pdf_url"), result.get("document_url"), result.get("cover_url"),
        result.get("quality_score", 0) >= 80,
    )
    ready = all(required)
    result["publication_ready"] = ready
    result["publication_status"] = "ready_to_sell" if ready else "not_ready"
    return result


def parse_chat_command(message: str) -> dict[str, Any] | None:
    text = " ".join(message.strip().split())
    lower = text.lower()
    for prefix in ("crie um ebook sobre ", "criar ebook sobre "):
        if lower.startswith(prefix):
            topic = text[len(prefix):].strip()
            return {"action": "create_product", "topic": topic} if topic else None
    match = re.search(r"(?:mude|mudar|altere|alterar) o preço.*?r\$\s*([0-9]+(?:[.,][0-9]{1,2})?)", lower)
    if match:
        return {"action": "set_price", "price": float(match.group(1).replace(",", "."))}
    return None
