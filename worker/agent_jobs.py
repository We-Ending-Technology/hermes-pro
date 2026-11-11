from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from backend.app.agents.orchestrator import run_chief
from backend.app.core.config import Settings
from backend.app.services.persistence import PersistentStore

logger = logging.getLogger("hermes.agent-worker")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _safe_select(store: PersistentStore, table: str, params: dict) -> list[dict]:
    try:
        rows = await store.db.select(table, params=params)
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        logger.warning("operational context read failed table=%s error=%s", table, str(exc)[:180])
        return []


async def build_operational_context(store: PersistentStore, settings: Settings) -> dict:
    """Collect bounded, non-sensitive operational facts for the Chief and specialists."""
    products, jobs, sales, health = await asyncio.gather(
        _safe_select(store, "hermes_products", {
            "select": "id,title,topic,status,current_stage,updated_at",
            "order": "updated_at.desc",
            "limit": "30",
        }),
        _safe_select(store, "hermes_jobs", {
            "select": "id,job_type,status,attempts,max_attempts,error_message,updated_at",
            "order": "updated_at.desc",
            "limit": "30",
        }),
        _safe_select(store, "hermes_sales_events", {
            "select": "provider,event_type,amount,currency,occurred_at",
            "order": "occurred_at.desc",
            "limit": "30",
        }),
        _safe_select(store, "hermes_system_health", {
            "select": "component,status,message,checked_at",
            "order": "checked_at.desc",
            "limit": "20",
        }),
    )

    product_counts: dict[str, int] = {}
    for row in products:
        status = str(row.get("status") or "unknown")
        product_counts[status] = product_counts.get(status, 0) + 1

    job_counts: dict[str, int] = {}
    for row in jobs:
        status = str(row.get("status") or "unknown")
        job_counts[status] = job_counts.get(status, 0) + 1

    provider = str(getattr(settings, "ai_provider", "unknown"))
    fallback = str(getattr(settings, "ai_fallback_provider", "") or "")
    fallback_configured = (
        (fallback == "openai" and bool(getattr(settings, "openai_api_key", None)))
        or (fallback == "gemini" and bool(
            getattr(settings, "gemini_api_key", None) or getattr(settings, "ai_api_key", None)
        ))
    )

    return {
        "captured_at": _now(),
        "provider": {
            "primary": provider,
            "fallback": fallback or None,
            "fallback_configured": fallback_configured,
            "model": (
                getattr(settings, "gemini_model", None) if provider == "gemini"
                else getattr(settings, "openai_chat_model", None) if provider == "openai"
                else None
            ),
        },
        "products": {
            "recent_count": len(products),
            "counts_by_status_in_recent_sample": product_counts,
            "recent": products[:10],
        },
        "jobs": {
            "recent_count": len(jobs),
            "counts_by_status_in_recent_sample": job_counts,
            "recent_failures": [
                {key: row.get(key) for key in ("id", "job_type", "status", "attempts", "error_message", "updated_at")}
                for row in jobs if row.get("status") in {"failed", "retrying"}
            ][:10],
        },
        "sales": {
            "recent_event_count": len(sales),
            "approved_purchase_events": sum(
                1 for row in sales
                if str(row.get("event_type", "")).upper() == "PURCHASE_APPROVED"
            ),
            "recent": sales[:10],
        },
        "system_health": health,
    }


async def process_agent(job_id: str, store: PersistentStore, settings: Settings, queue) -> None:
    job = await store.get_job(job_id)
    if not job or job["job_type"] != "agent_run" or job["status"] in {"completed", "cancelled", "running"}:
        return

    attempts = int(job.get("attempts", 0))
    max_attempts = int(job.get("max_attempts", 3))
    if attempts >= max_attempts:
        await store.update_job(job_id, "failed", attempts=attempts, error_message="maximum attempts reached")
        await store.db.update("hermes_agent_runs", {
            "status": "failed",
            "error_message": "maximum attempts reached",
            "completed_at": _now(),
        }, where={"id": f"eq.{job_id}"})
        return

    attempts += 1
    payload = job.get("payload") or {}
    instruction = str(payload.get("instruction", "")).strip()
    if not instruction:
        await store.update_job(job_id, "failed", attempts=attempts, error_message="agent instruction is empty")
        await store.db.update("hermes_agent_runs", {
            "status": "failed",
            "error_message": "agent instruction is empty",
            "completed_at": _now(),
        }, where={"id": f"eq.{job_id}"})
        return

    try:
        started_at = _now()
        await store.update_job(job_id, "running", attempts=attempts, error_message=None)
        await store.db.update("hermes_agent_runs", {
            "status": "running",
            "started_at": started_at,
            "error_message": None,
        }, where={"id": f"eq.{job_id}"})

        operational_context = await build_operational_context(store, settings)
        enriched_instruction = (
            f"{instruction}\n\n"
            "DADOS OPERACIONAIS REAIS COLETADOS DO BANCO DO HERMES (JSON):\n"
            f"{json.dumps(operational_context, ensure_ascii=False, default=str)}\n\n"
            "Use esses dados como evidência principal. Diferencie contagens da amostra recente "
            "de totais históricos. Não diga que faltam logs ou telemetria quando os dados acima "
            "respondem à pergunta. Se algum campo estiver vazio, declare apenas aquela lacuna."
        )
        result = await run_chief(enriched_instruction, settings)
        completed_at = _now()
        # Replace model-reported timing with authoritative persisted-job timings.
        start_dt = datetime.fromisoformat(started_at)
        end_dt = datetime.fromisoformat(completed_at)
        created_raw = job.get("created_at") or started_at
        created_dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
        sao_paulo = ZoneInfo("America/Sao_Paulo")
        timestamps = result.get("timestamps")
        if not isinstance(timestamps, dict):
            timestamps = {}
        timestamps.update({
            "utc": start_dt.isoformat(),
            "america_sao_paulo": start_dt.astimezone(sao_paulo).isoformat(),
            "completed_at_utc": end_dt.isoformat(),
            "completed_at_america_sao_paulo": end_dt.astimezone(sao_paulo).isoformat(),
            "pre_final_attempt_seconds": round(max(0.0, (start_dt - created_dt).total_seconds()), 2),
            "attempt_count": attempts,
            "execution_time_seconds": round(max(0.0, (end_dt - start_dt).total_seconds()), 2),
            "total_elapsed_seconds": round(max(0.0, (end_dt - created_dt).total_seconds()), 2),
        })
        result["timestamps"] = timestamps
        result["operational_context"] = operational_context
        await store.db.update("hermes_agent_runs", {
            "status": "completed",
            "output": result,
            "completed_at": completed_at,
            "error_message": None,
        }, where={"id": f"eq.{job_id}"})
        await store.update_job(job_id, "completed", attempts=attempts, error_message=None)
    except Exception as exc:
        message = str(exc)[:1000]
        if attempts < max_attempts:
            await store.update_job(job_id, "retrying", attempts=attempts, error_message=message)
            await store.db.update("hermes_agent_runs", {
                "status": "pending",
                "error_message": message,
            }, where={"id": f"eq.{job_id}"})
            logger.warning("agent job deferred to persistent recovery scan job=%s attempt=%s", job_id, attempts)
        else:
            await store.update_job(job_id, "failed", attempts=attempts, error_message=message)
            await store.db.update("hermes_agent_runs", {
                "status": "failed",
                "error_message": message,
                "completed_at": _now(),
            }, where={"id": f"eq.{job_id}"})
            logger.exception("agent job failed job=%s", job_id)
