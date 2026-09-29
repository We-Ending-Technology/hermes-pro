from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..services.opportunities import fetch_opportunities, score_opportunity


class AutonomyService:
    def __init__(self, store, queue):
        self.store = store
        self.queue = queue

    async def cycle(self, minimum_score: int = 55) -> dict[str, Any]:
        opportunities = await fetch_opportunities(limit=40)
        selected = []
        for item in opportunities:
            scored = score_opportunity(item)
            if scored["score"] < minimum_score:
                continue
            payload = {
                "opportunity_id": item.fingerprint,
                "source": item.source,
                "external_id": item.external_id,
                "title": item.title,
                "url": item.url,
                "description": item.description,
                "tags": item.tags,
                "budget": item.budget,
                "currency": item.currency,
                "discovery_automation_allowed": item.discovery_automation_allowed,                    "application_automation_allowed": False,
                "score": scored["score"],
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "next_action": "prepare" if item.discovery_automation_allowed else "manual_review",
            }
            key = f"opportunity:{item.fingerprint}"
            existing = await self.store.create_job_if_absent("opportunity_pipeline", payload, key)
            if existing:
                await self.queue.enqueue(str(existing["id"]))
                selected.append(payload)
        return {
            "status": "completed",
            "scanned": len(opportunities),
            "queued": len(selected),
            "opportunities": selected,
        }
