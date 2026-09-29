from __future__ import annotations
import asyncio
import logging
from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.autonomy import AutonomyService
from backend.app.services.persistence import PersistentStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes.autonomy.cron")

async def main() -> None:
    settings = get_settings()
    if not settings.autonomy_enabled:
        logger.info("autonomy disabled")
        return
    store = PersistentStore(SupabaseREST(settings))
    queue = JobQueue(settings.redis_url)
    try:
        result = await AutonomyService(store, queue).cycle(settings.autonomy_min_score)
        logger.info("autonomy cycle: scanned=%s queued=%s", result["scanned"], result["queued"])
    finally:
        await queue.close()

if __name__ == "__main__":
    asyncio.run(main())
