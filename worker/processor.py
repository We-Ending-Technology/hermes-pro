import asyncio
import logging
from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import get_settings
from backend.app.factory_service import FactoryService
from backend.app.repositories import SupabaseRepository, PersistentJobStore, PersistentProductStore
from backend.app.planner import TopicPlanner
from datetime import date

logger = logging.getLogger("hermes.worker")

class PersistentWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.repository = SupabaseRepository(self.settings)
        self.jobs = PersistentJobStore(self.repository)
        self.factory = FactoryService(build_ai_gateway(self.settings), PersistentProductStore(self.repository), repository=self.repository, storage_bucket=self.settings.storage_bucket)
        self.planner = TopicPlanner(self.factory.gateway)
        self.auto_date = date.today()
        self.auto_created = 0

    async def maybe_enqueue_topic(self) -> None:
        if not self.settings.auto_production_enabled or not self.settings.supabase_configured:
            return
        if date.today() != self.auto_date:
            self.auto_date, self.auto_created = date.today(), 0
        if self.auto_created >= self.settings.auto_production_daily_limit:
            return
        if await self.jobs.pending():
            return
        topic = await self.planner.next_topic()
        await self.jobs.create("product_factory", {"topic": topic})
        self.auto_created += 1

    async def process_once(self) -> int:
        if not self.settings.supabase_configured:
            logger.warning("worker idle: Supabase is not configured")
            return 0
        await self.maybe_enqueue_topic()
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
