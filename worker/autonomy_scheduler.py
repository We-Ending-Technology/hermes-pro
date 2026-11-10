from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import Settings
from backend.app.schemas_ext import is_kiwify_publishable_product
from backend.app.services.persistence import PersistentStore

logger = logging.getLogger("hermes.autonomy")

ACTIVE_PRODUCT_STATUSES = {"queued", "generating", "generating_artifacts"}
MAX_AUTOMATIC_REBUILDS_PER_PRODUCT = 2


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


async def supervision_tick(settings: Settings, store: PersistentStore, queue) -> dict[str, Any]:
    """Queue one persistent Chief review only when actionable exceptions exist."""
    if not settings.autonomy_enabled:
        return {"status": "disabled"}

    jobs = await store.list_jobs()
    products = await store.list_products()

    def source_of(job: dict[str, Any]) -> str:
        return str((job.get("payload") or {}).get("source") or "")

    def is_supervisor_run(job: dict[str, Any]) -> bool:
        return job.get("job_type") == "agent_run" and source_of(job).startswith("autonomous_supervision")

    def age_seconds(job: dict[str, Any]) -> float | None:
        try:
            updated = datetime.fromisoformat(str(job.get("updated_at")).replace("Z", "+00:00"))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            return max(0, (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return None

    def is_stale(job: dict[str, Any]) -> bool:
        age = age_seconds(job)
        return age is not None and age >= 600

    failed_jobs = [
        job for job in jobs
        if job.get("status") == "failed"
        and job.get("job_type") in {"product_generation", "agent_run"}
        and not is_supervisor_run(job)
    ][:5]
    review_products = [
        product for product in products if product.get("status") == "review_required"
    ][:5]
    stale_jobs = [
        job for job in jobs
        if job.get("status") in {"pending", "retrying"}
        and job.get("job_type") in {"product_generation", "agent_run"}
        and not is_supervisor_run(job)
        and is_stale(job)
    ][:5]
    if not failed_jobs and not review_products and not stale_jobs:
        return {"status": "no_actionable_findings"}

    evidence = {
        "failed_jobs": [
            {"id": str(job.get("id")), "type": job.get("job_type"), "error": str(job.get("error_message") or "")[:300], "updated_at": job.get("updated_at")}
            for job in failed_jobs
        ],
        "review_required_products": [
            {"id": str(product.get("id")), "title": product.get("title"), "topic": product.get("topic"), "updated_at": product.get("updated_at"), "quality_score": (product.get("metadata") or {}).get("quality_score")}
            for product in review_products
        ],
        "queued_or_retrying_jobs": [
            {"id": str(job.get("id")), "type": job.get("job_type"), "status": job.get("status"), "updated_at": job.get("updated_at")}
            for job in stale_jobs
        ],
    }
    fingerprint = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]
    source = "autonomous_supervision:" + fingerprint
    evidence_ids = {
        str(item["id"])
        for group in evidence.values()
        for item in group
    }
    previous = [
        job for job in jobs
        if is_supervisor_run(job)
        and (source_of(job) == source or (source_of(job) == "autonomous_supervision" and evidence_ids and all(identifier in str((job.get("payload") or {}).get("instruction") or "") for identifier in evidence_ids)))
    ]
    if previous:
        previous.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        latest = previous[0]
        status = latest.get("status")
        if status == "completed":
            return {"status": "already_reviewed", "run_id": str(latest["id"])}
        if status in {"pending", "running", "retrying"}:
            return {"status": "already_queued", "run_id": str(latest["id"])}
        if status == "failed" and (age_seconds(latest) or 0) < 6 * 60 * 60:
            return {"status": "retry_cooldown", "run_id": str(latest["id"])}

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    retry_window = int(now_dt.timestamp() // (6 * 60 * 60))
    instruction = (
        "Faça uma auditoria operacional do Hermes Pro usando somente estas evidências do banco. "
        "Identifique causa provável, prioridade, ação corretiva e como validar. "
        "Não altere produtos, não publique, não gaste dinheiro e não invente que corrigiu algo. "
        "Se um ebook estiver em review_required, explique o bloqueio editorial e como reescrever. "
        "Evidências: " + json.dumps(evidence, ensure_ascii=False)
    )
    job = await store.create_agent_job(
        instruction,
        source=source,
        now=now,
        idempotency_key="autonomy-chief:" + fingerprint + ":" + str(retry_window),
    )
    if job.get("status") in {"completed", "failed", "cancelled"}:
        return {"status": "already_reviewed", "run_id": str(job["id"])}
    await queue.enqueue_agent(str(job["id"]))
    return {
        "status": "supervision_queued",
        "run_id": str(job["id"]),
        "evidence_counts": {
            "failed_jobs": len(failed_jobs),
            "review_required_products": len(review_products),
            "queued_or_retrying_jobs": len(stale_jobs),
        },
    }

def _deterministic_content_gate_passed(metadata: dict) -> bool:
    gate = metadata.get("quality_gate") or {}
    try:
        chapter_counts = gate.get("chapter_word_counts") or []
        return (
            not gate.get("findings")
            and int(gate.get("word_count") or 0) >= 3500
            and int(gate.get("chapter_count") or 0) >= 8
            and int(gate.get("illustration_count") or 0) >= 4
            and int(gate.get("introduction_words") or 0) >= 200
            and int(gate.get("conclusion_words") or 0) >= 200
            and len(chapter_counts) >= 8
            and all(int(item.get("words") or 0) >= 300 for item in chapter_counts)
            and isinstance(metadata.get("content_data"), dict)
        )
    except (TypeError, ValueError, AttributeError):
        return False


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

    review_backlog = [p for p in products if p.get("status") == "review_required"]
    rebuild_candidates = []
    for product in products:
        if product.get("status") not in {"review_required", "failed"}:
            continue
        metadata = product.get("metadata") or {}
        quality_gate = metadata.get("quality_gate") or {}
        try:
            rebuild_attempts = int(metadata.get("rebuild_attempts") or 0)
        except (TypeError, ValueError):
            rebuild_attempts = MAX_AUTOMATIC_REBUILDS_PER_PRODUCT
        if (
            metadata.get("artifact_status") == "revision_required"
            and quality_gate.get("approved") is False
            and rebuild_attempts < MAX_AUTOMATIC_REBUILDS_PER_PRODUCT
            and not metadata.get("paused")
            and str(product.get("topic") or "").strip()
        ):
            rebuild_candidates.append(product)

    if rebuild_candidates:
        jobs = await store.list_jobs()
        active_product_ids = {
            str((job.get("payload") or {}).get("product_id"))
            for job in jobs
            if job.get("job_type") == "product_generation"
            and job.get("status") in {"pending", "running", "retrying"}
            and (job.get("payload") or {}).get("product_id")
        }
        rebuild_candidates = [
            product for product in rebuild_candidates
            if str(product.get("id")) not in active_product_ids
        ]
        if rebuild_candidates:
            rebuild_candidates.sort(key=lambda item: str(item.get("created_at") or ""))
            candidate = rebuild_candidates[0]
            try:
                candidate_metadata = candidate.get("metadata") or {}
                validation_attempts = int(candidate_metadata.get("validation_attempts") or 0)
                if _deterministic_content_gate_passed(candidate_metadata) and validation_attempts < 1:
                    updated_product, rebuild_job = await store.create_product_validation_job(str(candidate["id"]))
                    result_status = "review_product_validation_queued"
                    attempt_number = (updated_product.get("metadata") or {}).get("validation_attempts")
                    logger.info(
                        "review-required ebook content validation queued product=%s job=%s attempt=%s",
                        candidate["id"], rebuild_job["id"], attempt_number,
                    )
                else:
                    updated_product, rebuild_job = await store.create_product_rebuild_job(str(candidate["id"]))
                    result_status = "review_product_rebuild_queued"
                    attempt_number = (updated_product.get("metadata") or {}).get("rebuild_attempts")
                    logger.info(
                        "review-required ebook rebuild queued product=%s job=%s attempt=%s",
                        candidate["id"], rebuild_job["id"], attempt_number,
                    )
                await queue.enqueue(str(rebuild_job["id"]))
                return {
                    "status": result_status,
                    "product_id": str(candidate["id"]),
                    "job_id": str(rebuild_job["id"]),
                    "attempt": attempt_number,
                    "remaining_review_required": max(0, len(review_backlog) - (1 if candidate.get("status") == "review_required" else 0)),
                }
            except Exception:
                logger.exception("automatic review-required ebook validation/rebuild failed product=%s", candidate.get("id"))
                return {"status": "review_product_rebuild_error", "product_id": str(candidate.get("id"))}

    if len(review_backlog) >= settings.autonomy_max_review_required_products:
        return {"status": "review_backlog_full", "review_required": len(review_backlog)}

    ready = [p for p in products if is_kiwify_publishable_product(p)]
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
