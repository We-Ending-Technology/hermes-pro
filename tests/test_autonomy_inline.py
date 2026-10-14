import pytest

from backend.app.services.autonomy import AutonomyService
from backend.app.services.opportunities import Opportunity


class FakeStore:
    def __init__(self):
        self.jobs = []
        self.opportunities = []

    async def create_opportunity_if_absent(self, values):
        self.opportunities.append(values)
        return values

    async def create_job_if_absent(self, job_type, payload, key):
        job = {"id": "job-inline-1", "job_type": job_type, "status": "pending", "payload": payload, "idempotency_key": key}
        self.jobs.append(job)
        return job


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, job_id):
        self.jobs.append(job_id)


@pytest.mark.asyncio
async def test_inline_autonomy_cycle_persists_without_redis_enqueue(monkeypatch):
    opportunity = Opportunity(
        source="remotive",
        external_id="sample-job-1",
        title="Python API automation",
        url="https://example.com/jobs/sample-job-1",
        description="Build a Python API integration.",
        tags=["python", "api", "automation"],
        budget=250.0,
        currency="USD",
        discovery_automation_allowed=True,
        raw={"id": "sample-job-1"},
    )

    async def fake_fetch_opportunities(limit=40):
        return [opportunity]

    monkeypatch.setattr("backend.app.services.autonomy.fetch_opportunities", fake_fetch_opportunities)
    store = FakeStore()
    queue = FakeQueue()

    result = await AutonomyService(store, queue).cycle(0, enqueue_jobs=False)

    assert result["status"] == "completed"
    assert result["scanned"] == 1
    assert result["queued"] == 1
    assert result["opportunities"][0]["job_id"] == "job-inline-1"
    assert store.jobs[0]["job_type"] == "opportunity_pipeline"
    assert len(store.opportunities) == 1
    assert store.opportunities[0]["source"] == "remotive"
    assert store.opportunities[0]["url"] == "https://example.com/jobs/sample-job-1"
    assert queue.jobs == []
