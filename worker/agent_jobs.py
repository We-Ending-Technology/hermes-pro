from __future__ import annotations

import logging

from backend.app.agents.orchestrator import run_chief
from backend.app.core.config import Settings
from backend.app.services.persistence import PersistentStore

logger = logging.getLogger("hermes.agent-worker")


async def process_agent(job_id: str, store: PersistentStore, settings: Settings, queue) -> None:
    job = await store.get_job(job_id)
    if not job or job["job_type"] != "agent_run" or job["status"] in {"completed", "cancelled"}:
        return
    attempts = int(job.get("attempts", 0)) + 1
    payload = job.get("payload") or {}
    instruction = str(payload.get("instruction", "")).strip()
    if not instruction:
        await store.update_job(job_id, "failed", attempts=attempts, error_message="agent instruction is empty")
        return
    try:
        await store.update_job(job_id, "running", attempts=attempts, error_message=None)
        result = await run_chief(instruction, settings)
        await store.db.update("hermes_agent_runs", {
            "status": "completed",
            "output": result,
            "completed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }, where={"job_id": f"eq.{job_id}"})
        await store.update_job(job_id, "completed", attempts=attempts)
    except Exception as exc:
        message = str(exc)[:1000]
        if attempts < int(job.get("max_attempts", 3)):
            await store.update_job(job_id, "retrying", attempts=attempts, error_message=message)
            await queue.enqueue_agent(job_id)
        else:
            await store.update_job(job_id, "failed", attempts=attempts, error_message=message)
            await store.db.update("hermes_agent_runs", {
                "status": "failed",
                "error_message": message,
                "completed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            }, where={"job_id": f"eq.{job_id}"})
            logger.exception("agent job failed job=%s", job_id)
