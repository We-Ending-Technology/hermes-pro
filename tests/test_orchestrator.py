import pytest

from backend.app.services.orchestrator import AutonomousOrchestrator


class FakeCommerce:
    def __init__(self):
        self.opportunities = [{
            "id": "opp-1",
            "type": "product",
            "title": "Guia de produtividade",
            "score": 82,
            "confidence": 1.0,
            "status": "discovered",
            "metadata": {},
        }]
        self.events = []

    async def list_opportunities(self):
        return self.opportunities

    async def record_event(self, *args, **kwargs):
        self.events.append((args, kwargs))


class FakeStore:
    def __init__(self):
        self.created = []

    async def create_product_and_job(self, topic, metadata, idempotency_key):
        product = {"id": "product-1", "topic": topic}
        job = {"id": "job-1"}
        self.created.append((topic, metadata, idempotency_key))
        return product, job


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, job_id):
        self.jobs.append(job_id)


class FakeControls:
    def is_allowed(self, action, estimated_cost=0.0):
        return type("Decision", (), {"allowed": True, "reason": "allowed"})()


@pytest.mark.asyncio
async def test_cycle_turns_a_high_confidence_product_opportunity_into_one_job():
    commerce = FakeCommerce()
    store = FakeStore()
    queue = FakeQueue()
    orchestrator = AutonomousOrchestrator(commerce, store, queue, FakeControls(), min_score=75)

    result = await orchestrator.run_cycle()

    assert result["created_jobs"] == 1
    assert store.created[0][0] == "Guia de produtividade"
    assert queue.jobs == ["job-1"]
    assert commerce.opportunities[0]["status"] == "selected"


@pytest.mark.asyncio
async def test_cycle_does_not_create_a_job_for_low_score_opportunity():
    commerce = FakeCommerce()
    commerce.opportunities[0]["score"] = 40
    store = FakeStore()
    orchestrator = AutonomousOrchestrator(commerce, store, FakeQueue(), FakeControls(), min_score=75)

    result = await orchestrator.run_cycle()

    assert result["created_jobs"] == 0
    assert store.created == []
