from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.app.agents.orchestrator import run_chief
from backend.app.core.config import Settings
from backend.app.services.persistence import PersistentStore

logger = logging.getLogger("hermes.agent-worker")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

        result = await run_chief(instruction, settings)
        completed_at = _now()
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
