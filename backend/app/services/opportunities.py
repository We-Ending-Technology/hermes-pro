from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..db.supabase import SupabaseREST
from ..domain.opportunities import score_opportunity


class OpportunityService:
    def __init__(self, db: SupabaseREST) -> None:
        self.db = db

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = payload.get("idempotency_key")
        if key:
            existing = await self.db.select(
                "hermes_opportunities",
                params={"select": "*", "idempotency_key": f"eq.{key}", "limit": "1"},
            )
            if existing:
                return existing[0]
        now = datetime.now(timezone.utc).isoformat()
        result = await self.db.insert(
            "hermes_opportunities",
            {
                "type": payload["type"],
                "title": payload["title"],
                "description": payload.get("description"),
                "source": payload.get("source"),
                "source_url": payload.get("source_url"),
                "signals": payload.get("signals") or {},
                "status": payload.get("status", "discovered"),
                "idempotency_key": key,
                "metadata": payload.get("metadata") or {},
                "created_at": now,
                "updated_at": now,
            },
        )
        return result

    async def list(self, limit: int = 50) -> list[dict[str, Any]]:
        return await self.db.select(
            "hermes_opportunities",
            params={"select": "*", "order": "score.desc.nullslast,created_at.desc", "limit": str(limit)},
        )

    async def get(self, opportunity_id: str) -> dict[str, Any] | None:
        rows = await self.db.select(
            "hermes_opportunities",
            params={"select": "*", "id": f"eq.{opportunity_id}", "limit": "1"},
        )
        return rows[0] if rows else None

    async def score(self, opportunity_id: str) -> dict[str, Any]:
        opportunity = await self.get(opportunity_id)
        if not opportunity:
            raise KeyError(opportunity_id)
        result = score_opportunity(opportunity.get("signals") or {})
        now = datetime.now(timezone.utc).isoformat()
        await self.db.update(
            "hermes_opportunities",
            {"score": result["score"], "confidence": result["confidence"], "updated_at": now},
            where={"id": f"eq.{opportunity_id}"},
        )
        await self.db.insert(
            "hermes_opportunity_scores",
            {
                "opportunity_id": opportunity_id,
                "score": result["score"],
                "confidence": result["confidence"],
                "dimensions": result["dimensions"],
                "findings": result["findings"],
                "created_at": now,
            },
        )
        return result
