from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class MemoryEngine:
    """Evidence-backed persistent memory for verified operational lessons."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def record_candidate(self, category: str, statement: str, evidence: dict[str, Any], *, source_type: str | None = None, source_id: str | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return await self.db.insert("hermes_memories", {
            "category": category,
            "statement": statement.strip(),
            "evidence": evidence or {},
            "confidence": 0,
            "verification_count": 0,
            "status": "candidate",
            "source_type": source_type,
            "source_id": source_id,
            "created_at": now,
            "updated_at": now,
        })

    async def promote(self, memory_id: str, *, evidence: dict[str, Any]) -> dict[str, Any]:
        if not evidence.get("verified"):
            raise ValueError("memory promotion requires verified evidence")
        rows = await self.db.select("hermes_memories", params={"id": f"eq.{memory_id}", "limit": "1"})
        if not rows:
            raise ValueError("memory not found")
        row = rows[0]
        count = int(row.get("verification_count") or 0) + 1
        confidence = min(1.0, max(float(row.get("confidence") or 0), 0.7) + 0.1 * min(count, 3))
        return await self.db.update("hermes_memories", {
            "status": "active",
            "evidence": {**(row.get("evidence") or {}), **evidence},
            "verification_count": count,
            "confidence": confidence,
            "last_verified_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, where={"id": f"eq.{memory_id}"})

    async def retrieve(self, category: str | None = None, *, limit: int = 10) -> list[dict[str, Any]]:
        params = {"status": "active"}
        if category:
            params["category"] = category
        rows = await self.db.select("hermes_memories", params=params)
        rows = [row for row in rows if row.get("status") == "active" and (not category or row.get("category") == category)]
        rows.sort(key=lambda row: float(row.get("confidence") or 0), reverse=True)
        return rows[:limit]
