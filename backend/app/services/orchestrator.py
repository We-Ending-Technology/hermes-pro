from __future__ import annotations

from typing import Any


class AutonomousOrchestrator:
    """Converts verified opportunities into persistent jobs under autonomy policy."""

    def __init__(self, commerce: Any, store: Any, queue: Any, controls: Any, min_score: float = 75.0, memory: Any | None = None) -> None:
        self.commerce = commerce
        self.store = store
        self.queue = queue
        self.controls = controls
        self.min_score = min_score
        self.memory = memory

    async def run_cycle(self, limit: int = 5) -> dict[str, Any]:
        created_jobs = 0
        skipped = 0
        memory_consulted = False
        if self.memory is not None:
            await self.memory.retrieve("incident_resolution", limit=5)
            memory_consulted = True
        opportunities = await self.commerce.list_opportunities()
        for opportunity in opportunities:
            if created_jobs >= limit:
                break
            if opportunity.get("type") != "product" or opportunity.get("status") != "discovered":
                continue
            score = float(opportunity.get("score") or 0)
            confidence = float(opportunity.get("confidence") or 0)
            if score < self.min_score or confidence <= 0:
                skipped += 1
                continue
            decision = self.controls.is_allowed("produce", estimated_cost=0.0)
            if not decision.allowed:
                skipped += 1
                continue
            key = f"opportunity:{opportunity['id']}:product_generation"
            product, job = await self.store.create_product_and_job(
                str(opportunity["title"]),
                {"origin": "autonomous_radar", "opportunity_id": str(opportunity["id"]), "score": score, "confidence": confidence},
                key,
            )
            await self.queue.enqueue(str(job["id"]))
            await self.commerce.mark_opportunity_selected(str(opportunity["id"]))
            await self.commerce.record_event(
                "autonomous_job_created",
                {"opportunity_id": str(opportunity["id"]), "product_id": str(product["id"]), "job_id": str(job["id"]), "score": score, "confidence": confidence},
                idempotency_key=key,
            )
            created_jobs += 1
        return {"created_jobs": created_jobs, "skipped": skipped, "memory_consulted": memory_consulted}