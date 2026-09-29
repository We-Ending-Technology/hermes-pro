from __future__ import annotations

import asyncio

from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.commerce_store import CommerceStore
from backend.app.services.controls import ControlService
from backend.app.services.orchestrator import AutonomousOrchestrator
from backend.app.services.persistence import PersistentStore
from backend.app.services.radar_scheduler import run_radar_cycle


async def main() -> None:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_secret_key):
        raise SystemExit("Supabase is required for the Radar cron")
    db = SupabaseREST(settings)
    commerce = CommerceStore(db)
    store = PersistentStore(db)
    queue = JobQueue(settings.redis_url, db)
    orchestrator = AutonomousOrchestrator(commerce, store, queue, ControlService())
    try:
        print(await run_radar_cycle(commerce, db, orchestrator))
    finally:
        await queue.close()


if __name__ == "__main__":
    asyncio.run(main())
