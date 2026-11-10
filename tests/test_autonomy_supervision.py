from types import SimpleNamespace

import pytest

from worker.autonomy_scheduler import supervision_tick

class FakeStore:
    def __init__(self, products=None, jobs=None):
        self.products = products or []
        self.jobs = jobs or []
        self.created = []

    async def list_products(self):
        return self.products

    async def list_jobs(self):
        return self.jobs

    async def create_agent_job(self, instruction, source, now, idempotency_key=None):
        item = {"id": "chief-run-1", "status": "pending", "idempotency_key": idempotency_key}
        self.created.append((instruction, source, idempotency_key))
        return item

class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_agent(self, job_id):
        self.jobs.append(job_id)

@pytest.mark.asyncio
async def test_supervision_is_idle_without_actionable_work():
    store, queue = FakeStore(), FakeQueue()
    result = await supervision_tick(SimpleNamespace(autonomy_enabled=True), store, queue)
    assert result["status"] == "no_actionable_findings"
    assert store.created == []
    assert queue.jobs == []

@pytest.mark.asyncio
async def test_supervision_queues_persistent_chief_run_for_review_required_product():
    store = FakeStore(products=[{"id": "p-1", "title": "Ebook curto", "status": "review_required", "updated_at": "2026-11-10T10:00:00Z", "metadata": {"quality_score": 52}}])
    queue = FakeQueue()
    result = await supervision_tick(SimpleNamespace(autonomy_enabled=True), store, queue)
    assert result["status"] == "supervision_queued"
    assert result["run_id"] == "chief-run-1"
    assert store.created[0][1] == "autonomous_supervision"
    assert store.created[0][2].startswith("autonomy-chief:")
    assert queue.jobs == ["chief-run-1"]