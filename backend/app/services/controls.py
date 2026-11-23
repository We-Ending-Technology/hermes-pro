from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..db.supabase import SupabaseREST
from ..domain.controls import control_allows


class ControlService:
    def __init__(self, db: SupabaseREST) -> None:
        self.db = db

    async def get(self) -> dict[str, Any]:
        rows = await self.db.select("hermes_settings", params={"select": "*", "id": "eq.true", "limit": "1"})
        if rows:
            return rows[0]
        return {
            "id": True,
            "kill_switch": False,
            "paused_domains": [],
            "daily_ai_budget": None,
            "daily_ads_budget": None,
            "daily_total_budget": None,
            "human_approval_mode": "risk_based",
        }

    async def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = await self.get()
        merged = {**current, **payload, "id": True, "updated_at": datetime.now(timezone.utc).isoformat()}
        return await self.db.update("hermes_settings", merged, where={"id": "eq.true"})

    async def allows(self, action: str) -> tuple[bool, str]:
        settings = await self.get()
        return control_allows(action, settings)
