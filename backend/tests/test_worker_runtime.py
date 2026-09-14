from backend.app.worker_runtime import run_worker_cycle


class FakeQueue:
    def __init__(self):
        self.items = ["job-1"]

    async def dequeue(self, timeout=10):
        return self.items.pop(0) if self.items else None


class FakeStore:
    async def list_jobs(self):
        return []


async def fake_process_product(job_id, store, queue):
    return job_id


async def test_worker_cycle_processes_a_dequeued_job():
    result = await run_worker_cycle(FakeStore(), FakeQueue(), fake_process_product)
    assert result == "job-1"


async def test_worker_cycle_returns_none_when_queue_is_empty():
    queue = FakeQueue()
    await run_worker_cycle(FakeStore(), queue, fake_process_product)
    result = await run_worker_cycle(FakeStore(), queue, fake_process_product)
    assert result is None
