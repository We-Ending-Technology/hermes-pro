from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..agents.orchestrator import run_chief
from ..core.config import Settings
from ..db.supabase import SupabaseREST
from .persistence import PersistentStore


class AutonomyService:
    def __init__(self, settings: Settings, store: PersistentStore) -> None:
        self.settings = settings
        self.store = store

    async def run(self, instruction: str, source: str = "manual") -> dict[str, Any]:
        started = datetime.now(timezone.utc).isoformat()
        result = await run_chief(instruction, self.settings)
        return {
            "source": source,
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            **result,
        }

    async def create_job(self, instruction: str, source: str = "manual") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return await self.store.create_agent_job(instruction, source, now)
