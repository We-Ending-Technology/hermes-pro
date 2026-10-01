from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..db.supabase import SupabaseREST


class AgentMemory:
    def __init__(self, db: SupabaseREST) -> None:
        self.db = db

    async def remember(self, key: str, value: dict[str, Any], source: str = "agent") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return await self.db.upsert("hermes_agent_memory", {
            "key": key,
            "value": value,
            "source": source,
            "updated_at": now,
        }, conflict="key")

    async def recall(self, key: str) -> dict[str, Any] | None:
        rows = await self.db.select("hermes_agent_memory", params={"select": "*", "key": f"eq.{key}", "limit": "1"})
        return rows[0] if rows else None
