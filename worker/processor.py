import asyncio
import logging
from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import get_settings
from backend.app.factory_service import FactoryService
from backend.app.repositories import SupabaseRepository, PersistentJobStore, PersistentProductStore

logger = logging.getLogger("hermes.worker")

class PersistentWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.repository = SupabaseRepository(self.settings)
        self.jobs = PersistentJobStore(self.repository)
        self.factory = FactoryService(build_ai_gateway(self.settings), PersistentProductStore(self.repository))

    async def process_once(self) -> int:
        if not self.settings.supabase_configured:
            logger.warning("worker idle: Supabase is not configured")
            return 0
        processed = 0
        for job in await self.jobs.pending():
            job_id = job["id"]
            claimed = await self.jobs.update(job_id, status="running", attempts=job.get("attempts", 0) + 1)
            if claimed.get("status") != "running":
                continue
            try:
                await self.factory.produce(job["payload"]["topic"])
                await self.jobs.update(job_id, status="completed", error_message=None)
            except Exception as exc:
                attempts = int(job.get("attempts", 0)) + 1
                status = "retrying" if attempts < self.settings.max_job_retries else "failed"
                await self.jobs.update(job_id, status=status, attempts=attempts, error_message=str(exc))
                logger.exception("job %s failed", job_id)
            processed += 1
        return processed

    async def run_forever(self, interval: float = 10.0) -> None:
        while True:
            await self.process_once()
            await asyncio.sleep(interval)
