from __future__ import annotations

import asyncio
import logging

from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.persistence import PersistentStore
from backend.app.services.telegram import TelegramNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes.maintenance")

async def run() -> None:
    settings = get_settings()
    store = PersistentStore(SupabaseREST(settings))
    queue = JobQueue(settings.redis_url)
    telegram = TelegramNotifier(settings)
    try:
        jobs = await store.list_jobs()
        recoverable = [j for j in jobs if j["job_type"] == "product_generation" and j["status"] in {"pending", "retrying", "running"}]
        failed = [j for j in jobs if j["status"] == "failed"]
        if settings.hermes_kill_switch:
            logger.warning("kill switch active; maintenance will not enqueue jobs")
        else:
            for job in recoverable:
                if job["status"] in {"pending", "retrying"}:
                    await queue.enqueue(str(job["id"]))
                elif job["status"] == "running":
                    attempts = int(job.get("attempts") or 0)
                    if attempts < 3:
                        await store.update_job(str(job["id"]), "retrying", attempts=attempts, error_message="maintenance recovery: stale running job")
                        await queue.enqueue(str(job["id"]))
        if failed:
            message = f"Hermes maintenance: {len(failed)} job(s) failed; {len(recoverable)} recoverable."
            await telegram.send(message)
        logger.info("maintenance complete: recoverable=%s failed=%s kill_switch=%s", len(recoverable), len(failed), settings.hermes_kill_switch)
    finally:
        await queue.close()

if __name__ == "__main__":
    asyncio.run(run())
