import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.queue import JobQueue
from worker.main import recover_pending


class FakeRedis:
    def __init__(self):
        self.calls = []
        self.processing = []
    async def blmove(self, source, destination, timeout, src="LEFT", dest="RIGHT"):
        self.calls.append(("blmove", source, destination, timeout, src, dest))
        return '{"job_id":"job-1"}'
    async def lrem(self, key, count, value):
        self.calls.append(("lrem", key, count, value))
        return 1
    async def llen(self, key):
        return 0
    async def lpush(self, key, value):
        self.calls.append(("lpush", key, value))
        return 1


@pytest.mark.asyncio
async def test_queue_uses_atomic_move_to_processing_and_ack():
    queue = JobQueue("redis://localhost")
    queue.redis = FakeRedis()

    job_id = await queue.dequeue(timeout=2)
    await queue.ack(job_id)

    assert job_id == "job-1"
    assert queue.redis.calls[0] == (
        "blmove",
        "hermes:jobs:product_generation",
        "hermes:jobs:processing",
        2,
        "RIGHT",
        "LEFT",
    )
    assert queue.redis.calls[1][0:3] == ("lrem", "hermes:jobs:processing", 1)


class FakeStore:
    def __init__(self):
        self.cutoff = None
        self.updates = []
    async def list_recoverable_jobs(self, stale_before):
        self.cutoff = stale_before
        return [
            {"id": "stale-product", "job_type": "product_generation", "status": "running"},
            {"id": "stale-agent", "job_type": "agent_run", "status": "retrying"},
        ]
    async def update_job(self, job_id, status, **kwargs):
        self.updates.append((job_id, status, kwargs))
    async def record_worker_health(self, *args, **kwargs):
        pass


class FakeQueue:
    def __init__(self):
        self.calls = []
    async def remove_processing(self, job_id, *, agent=False):
        self.calls.append(("remove", job_id, agent))
    async def enqueue(self, job_id):
        self.calls.append(("product", job_id))
    async def enqueue_agent(self, job_id):
        self.calls.append(("agent", job_id))
    async def depths(self):
        return {"product": 0, "agent": 0}


@pytest.mark.asyncio
async def test_recovery_requeues_stale_running_and_retrying_jobs():
    store = FakeStore()
    queue = FakeQueue()

    await recover_pending(store, queue)

    age = (datetime.now(timezone.utc) - store.cutoff).total_seconds()
    assert 74 <= age <= 76
    assert ("stale-product", "retrying", {"error_message": "recovered after stale worker lease (>75s)"}) in store.updates
    assert ("remove", "stale-product", False) in queue.calls
    assert ("product", "stale-product") in queue.calls
    assert ("agent", "stale-agent") in queue.calls
