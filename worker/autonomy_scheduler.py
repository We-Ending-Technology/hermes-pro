from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import Settings
from backend.app.services.persistence import PersistentStore

logger = logging.getLogger("hermes.autonomy")

ACTIVE_PRODUCT_STATUSES = {"queued", "generating", "generating_artifacts"}
READY_PRODUCT_STATUSES = {"ready_to_publish", "review_required"}


def _json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text[3:]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    text = text.strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("autonomy candidate must be a JSON object")
    return value


def _created_today(product: dict[str, Any], today) -> bool:
    value = product.get("created_at")
    if not value:
        return False
    try:
        created = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created.astimezone(timezone.utc).date() == today
    except (TypeError, ValueError):
        return False


def _normalise_topic(value: str) -> str:
    return " ".join(value.casefold().split())


async def autonomy_tick(settings: Settings, store: PersistentStore, queue) -> dict[str, Any]:
    """Create at most one new product per tick, subject to explicit capacity limits."""
    if not settings.autonomy_enabled:
        return {"status": "disabled"}

    provider = (settings.ai_provider or "").strip().lower()
    primary_available = (
        provider == "gemini" and bool(settings.gemini_api_key or settings.ai_api_key)
    ) or (provider == "openai" and bool(settings.openai_api_key))
    fallback_provider = (settings.ai_fallback_provider or "").strip().lower()
    fallback_available = (
        fallback_provider == "gemini" and bool(settings.gemini_api_key or settings.ai_api_key)
    ) or (fallback_provider == "openai" and bool(settings.openai_api_key))
    if not primary_available and not fallback_available:
        return {"status": "blocked", "reason": "missing_all_configured_ai_keys"}

    products = await store.list_products()
    active = [p for p in products if p.get("status") in ACTIVE_PRODUCT_STATUSES]
    if len(active) >= settings.autonomy_max_active_products:
        return {"status": "capacity_full", "active_products": len(active)}

    ready = [p for p in products if p.get("status") in READY_PRODUCT_STATUSES]
    if len(ready) >= settings.autonomy_max_ready_to_publish:
        return {"status": "publication_backlog_full", "ready_to_publish": len(ready)}

    now = datetime.now(timezone.utc)
    today_products = [p for p in products if _created_today(p, now.date())]
    if len(today_products) >= settings.autonomy_max_daily_products:
        return {"status": "daily_limit_reached", "created_today": len(today_products)}

    existing_topics = sorted({_normalise_topic(str(p.get("topic", ""))) for p in products if p.get("topic")})
    prompt = (
        "Proponha UMA oportunidade de produto digital que o Hermes consiga produzir AGORA. "
        "Nesta fase, o pipeline de produção implementado gera e-books; portanto escolha um "
        "e-book prático, específico, original e vendável para público brasileiro. Não afirme "
        "que existe demanda, volume de busca ou potencial de vendas sem pesquisa verificável. "
        "Evite temas médicos, jurídicos, financeiros regulados, promessas de renda e alegações "
        "que exijam aconselhamento profissional. Não repita nem reformule os temas existentes. "
        f"Temas já cadastrados: {existing_topics[-100:]}. "
        "Retorne somente JSON válido com: topic (string curta e específica), rationale "
        "(motivo editorial, sem alegar dados de mercado), target_audience (string), "
        "differentiator (string)."
    )

    try:
        gateway = build_ai_gateway(settings)
        response = await gateway.complete(
            prompt,
            system="Você é o estrategista de portfólio Hermes. Seja conservador, específico e honesto. Retorne JSON válido.",
        )
        candidate = _json_object(response.content)
        topic = str(candidate.get("topic", "")).strip()
        if len(topic) < 12 or len(topic) > 240:
            raise ValueError("candidate topic length must be between 12 and 240 characters")
        if _normalise_topic(topic) in existing_topics:
            return {"status": "duplicate_rejected", "topic": topic}

        slot = len(today_products) + 1
        idempotency_key = f"autonomous-product:{now.date().isoformat()}:{slot}"
        product, job = await store.create_product_and_job(
            topic=topic,
            metadata={
                "source": "autonomous_factory",
                "product_type": "ebook",
                "candidate": candidate,
                "market_validation": "not_yet_verified",
                "publication_status": "not_published",
            },
            idempotency_key=idempotency_key,
        )
        await queue.enqueue(str(job["id"]))
        logger.info("autonomous product queued product=%s job=%s topic=%s", product["id"], job["id"], topic)
        return {"status": "product_queued", "product_id": str(product["id"]), "job_id": str(job["id"]), "topic": topic}
    except Exception:
        logger.exception("autonomous product discovery failed")
        return {"status": "error", "reason": "candidate_generation_failed"}
