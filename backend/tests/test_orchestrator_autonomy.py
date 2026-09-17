import pytest

from app.services.orchestrator import AutonomousOrchestrator


class Controls:
    def is_allowed(self, action, estimated_cost=0):
        return type("Decision", (), {"allowed": True, "reason": "allowed"})()


class Commerce:
    async def list_opportunities(self):
        return [{"id": "o1", "type": "product", "status": "discovered", "title": "AI guide", "score": 90, "confidence": 0.9}]
    async def mark_opportunity_selected(self, _): return {}
    async def record_event(self, *args, **kwargs): return {}


class Store:
    async def create_product_and_job(self, *args, **kwargs):
        return ({"id": "p1"}, {"id": "j1"})


class Queue:
    async def enqueue(self, _): return None


class Memory:
    async def retrieve(self, category=None, limit=10):
        return [{"statement": "Use verified product pipeline", "confidence": 0.9}]


@pytest.mark.asyncio
async def test_ceo_consults_memory_before_delegating():
    orchestrator = AutonomousOrchestrator(Commerce(), Store(), Queue(), Controls(), memory=Memory())
    result = await orchestrator.run_cycle(limit=1)
    assert result["created_jobs"] == 1
    assert result["memory_consulted"] is True
