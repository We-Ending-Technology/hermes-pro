from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ReflectionEngine:
    """Consolidates verified operational outcomes into durable memory."""

    def __init__(self, event_store: Any, memory: Any) -> None:
        self.event_store = event_store
        self.memory = memory

    async def run_once(self, *, trigger_type: str = "scheduled") -> dict[str, int]:
        events = await self.event_store.list_events()
        promoted = 0
        candidates = 0
        for event in events[-50:]:
            if event.get("event_type") != "incident_resolved":
                continue
            payload = event.get("payload") or {}
            cause = payload.get("cause")
            fix = payload.get("fix")
            if not cause or not fix:
                continue
            candidates += 1
            candidate = await self.memory.record_candidate(
                "incident_resolution",
                f"When {cause}, use {fix}.",
                {"event_id": event.get("id"), "cause": cause, "fix": fix},
                source_type="incident",
                source_id=str(event.get("id") or ""),
            )
            await self.memory.promote(candidate["id"], evidence={"verified": True, "event_id": event.get("id")})
            promoted += 1
        return {"candidates": candidates, "promoted": promoted, "timestamp": datetime.now(timezone.utc).isoformat()}
