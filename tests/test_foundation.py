import pytest
from backend.app.models.jobs import InMemoryJobStore, JobStatus
from backend.app.product_factory import ProductFactory

@pytest.mark.asyncio
async def test_job_lifecycle_and_retry() -> None:
    store = InMemoryJobStore()
    job = store.create("document", {"topic": "Hermes"})
    assert job.status == JobStatus.PENDING
    store.mark_running(job)
    assert job.status == JobStatus.RUNNING
    store.mark_failed(job, "temporary error")
    assert job.status == JobStatus.RETRYING
    store.mark_running(job)
    store.mark_completed(job)
    assert job.status == JobStatus.COMPLETED
    assert job.attempts == 2

@pytest.mark.parametrize(("score", "decision"), [(80, "approved"), (99, "approved"), (79, "revision_required")])
def test_quality_gate(score: int, decision: str) -> None:
    assert ProductFactory().validate(score)["decision"] == decision

@pytest.mark.asyncio
async def test_ai_gateway_without_credentials() -> None:
    from backend.app.ai_gateway.factory import build_ai_gateway
    from backend.app.core.config import Settings
    result = await build_ai_gateway(Settings(ai_provider="stub")).complete("ping")
    assert result.provider == "stub"
