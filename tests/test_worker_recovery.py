from datetime import datetime, timedelta, timezone

import pytest

from worker.main import recover_pending


class FakeStore:
    def __init__(self, job):
        self.job = dict(job)
        self.updates = []

    async def list_recoverable_jobs(self, stale_before):
        updated_at = datetime.fromisoformat(self.job["updated_at"])
        if self.job["status"] in {"pending", "retrying", "running"} and updated_at < stale_before:
            return [dict(self.job)]
        return []

    async def update_job(self, job_id, status, *, attempts=None, error_message=None):
        self.updates.append((job_id, status))
        self.job["status"] = status
        self.job["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.job["error_message"] = error_message
        if attempts is not None:
            self.job["attempts"] = attempts
        return dict(self.job)


class FakeQueue:
    def __init__(self):
        self.normal = []
        self.priority = []
        self.agents = []
        self.removed_processing = []

    async def enqueue(self, job_id):
        self.normal.append(job_id)

    async def enqueue_priority(self, job_id):
        self.priority.append(job_id)

    async def enqueue_agent(self, job_id):
        self.agents.append(job_id)

    async def remove_processing(self, job_id, *, agent=False):
        self.removed_processing.append((job_id, agent))

    async def depths(self):
        return {"product": len(self.normal) + len(self.priority), "agent": len(self.agents)}


def stale_job(*, status="pending", priority=False):
    return {
        "id": "job-1",
        "job_type": "product_generation",
        "status": status,
        "attempts": 1,
        "error_message": "previous transient error",
        "payload": {"product_id": "product-1", "topic": "test", "priority": priority},
        "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
    }


@pytest.mark.asyncio
async def test_recovery_refreshes_lease_and_does_not_enqueue_same_job_repeatedly():
    store = FakeStore(stale_job())
    queue = FakeQueue()

    await recover_pending(store, queue)
    await recover_pending(store, queue)

    assert queue.normal == ["job-1"]
    assert queue.priority == []
    assert store.updates == [("job-1", "pending")]


@pytest.mark.asyncio
async def test_priority_pilot_job_is_placed_at_next_dequeue_position():
    store = FakeStore(stale_job(priority=True))
    queue = FakeQueue()

    await recover_pending(store, queue)

    assert queue.priority == ["job-1"]
    assert queue.normal == []
    assert store.updates == [("job-1", "pending")]


@pytest.mark.asyncio
async def test_stale_running_job_is_removed_from_processing_and_requeued_once():
    store = FakeStore(stale_job(status="running", priority=True))
    queue = FakeQueue()

    await recover_pending(store, queue)
    await recover_pending(store, queue)

    assert store.updates == [("job-1", "retrying"), ("job-1", "pending")]
    assert queue.removed_processing == [("job-1", False)]
    assert queue.priority == ["job-1"]
