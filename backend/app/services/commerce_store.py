from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..db.supabase import SupabaseREST


class CommerceStore:
    def __init__(self, db: SupabaseREST) -> None:
        self.db = db

    async def create_opportunity(self, data: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        if idempotency_key:
            rows = await self.db.select("hermes_opportunities", params={"select": "*", "idempotency_key": f"eq.{idempotency_key}", "limit": "1"})
            if rows:
                return rows[0]
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "type": data.get("type", "product"), "title": str(data["title"]).strip(),
            "description": data.get("description"), "source": data.get("source"),
            "source_url": data.get("source_url"), "signals": data.get("signals", {}),
            "score": data.get("score"), "confidence": data.get("confidence"),
            "status": data.get("status", "discovered"), "idempotency_key": idempotency_key,
            "metadata": data.get("metadata", {}), "created_at": now, "updated_at": now,
        }
        return await self.db.insert("hermes_opportunities", payload)

    async def list_opportunities(self) -> list[dict[str, Any]]:
        return await self.db.select("hermes_opportunities", params={"select": "*", "order": "score.desc,created_at.desc"})

    async def mark_opportunity_selected(self, opportunity_id: str) -> dict[str, Any]:
        return await self.db.update(
            "hermes_opportunities",
            {"status": "selected", "updated_at": datetime.now(timezone.utc).isoformat()},
            where={"id": f"eq.{opportunity_id}"},
        )

    async def record_expense(self, category: str, amount: float, description: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.db.insert("hermes_expenses", {"category": category, "amount": amount, "description": description, "metadata": metadata or {}, "occurred_at": datetime.now(timezone.utc).isoformat()})

    async def record_event(self, event_type: str, payload: dict[str, Any], provider: str = "hermes", idempotency_key: str | None = None) -> dict[str, Any]:
        if idempotency_key:
            existing = await self.db.select("hermes_events", params={"select": "*", "idempotency_key": f"eq.{idempotency_key}", "limit": "1"})
            if existing:
                return existing[0]
        return await self.db.insert("hermes_events", {"event_type": event_type, "provider": provider, "payload": payload, "idempotency_key": idempotency_key, "occurred_at": datetime.now(timezone.utc).isoformat()})

    async def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self.db.select("hermes_events", params={"select": "*", "order": "occurred_at.desc", "limit": str(limit)})

    async def list_expenses(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self.db.select("hermes_expenses", params={"select": "*", "order": "occurred_at.desc", "limit": str(limit)})

    async def get_settings(self) -> dict[str, Any]:
        rows = await self.db.select("hermes_settings", params={"select": "*", "limit": "1"})
        return rows[0] if rows else {}
