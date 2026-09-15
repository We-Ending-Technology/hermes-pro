from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..db.supabase import SupabaseREST


class ServiceOpportunityService:
    def __init__(self, db: SupabaseREST) -> None:
        self.db = db

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        value = float(payload.get("estimated_value") or 0)
        cost = float(payload.get("estimated_cost") or 0)
        result = await self.db.insert(
            "hermes_services",
            {
                "opportunity_id": payload.get("opportunity_id"),
                "title": payload["title"],
                "briefing": payload.get("briefing"),
                "status": payload.get("status", "candidate"),
                "difficulty": payload.get("difficulty"),
                "estimated_hours": payload.get("estimated_hours"),
                "estimated_value": value,
                "estimated_cost": cost,
                "estimated_profit": round(value - cost, 2),
                "metadata": payload.get("metadata") or {},
                "created_at": now,
                "updated_at": now,
            },
        )
        return result

    async def list(self, limit: int = 50) -> list[dict[str, Any]]:
        return await self.db.select(
            "hermes_services",
            params={"select": "*", "order": "estimated_profit.desc.nullslast,created_at.desc", "limit": str(limit)},
        )
