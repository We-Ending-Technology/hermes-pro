from backend.app.queue import JobQueue


class FakeDB:
    async def select(self, table, *, params=None):
        assert table == "hermes_jobs"
        return [{"id": "job-42", "status": "pending", "attempts": 0, "max_attempts": 3}]


async def test_queue_uses_persistent_fallback_without_redis():
    queue = JobQueue("", FakeDB())
    assert queue.uses_redis is False
    await queue.enqueue("job-42")
    assert await queue.dequeue() == "job-42"


async def test_localhost_redis_is_not_used_in_production_fallback():
    queue = JobQueue("redis://localhost:6379/0", FakeDB())
    assert queue.uses_redis is False
