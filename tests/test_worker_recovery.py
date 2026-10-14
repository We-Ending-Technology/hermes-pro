import pytest

from worker.main import process_opportunity, recover_pending


class FakeStore:
    def __init__(self, jobs):
        self.jobs = jobs
        self.updated = []
        self.product_updates = []

    async def list_jobs(self):
        return self.jobs

    async def get_job(self, job_id):
        return next((job for job in self.jobs if str(job["id"]) == job_id), None)

    async def update_job(self, job_id, status, **kwargs):
        self.updated.append((job_id, status, kwargs))
        job = next((job for job in self.jobs if str(job["id"]) == job_id), None)
        if job:
            job["status"] = status
            job.update({k: v for k, v in kwargs.items() if v is not None})
        return job

    async def update_product(self, product_id, **kwargs):
        self.product_updates.append((product_id, kwargs))


class FakeQueue:
    def __init__(self):
        self.jobs = []
        self.agent_jobs = []

    async def enqueue(self, job_id):
        self.jobs.append(job_id)

    async def enqueue_agent(self, job_id):
        self.agent_jobs.append(job_id)


@pytest.mark.asyncio
async def test_recovery_fails_exhausted_job_without_requeueing():
    store = FakeStore([{
        "id": "job-1", "job_type": "opportunity_pipeline",
        "status": "running", "attempts": 3, "max_attempts": 3, "payload": {},
    }])
    queue = FakeQueue()

    await recover_pending(store, queue)

    assert store.updated[0][1] == "failed"
    assert queue.jobs == []
    assert queue.agent_jobs == []


@pytest.mark.asyncio
async def test_recovery_marks_interrupted_job_before_requeueing():
    store = FakeStore([{
        "id": "job-2", "job_type": "opportunity_pipeline",
        "status": "running", "attempts": 1, "max_attempts": 3, "payload": {},
    }])
    queue = FakeQueue()

    await recover_pending(store, queue)

    assert store.updated[0][1] == "retrying"
    assert "recovered at startup" in store.updated[0][2]["error_message"]
    assert queue.jobs == ["job-2"]


@pytest.mark.asyncio
async def test_opportunity_processor_does_not_exceed_retry_budget():
    store = FakeStore([{
        "id": "job-3", "job_type": "opportunity_pipeline",
        "status": "retrying", "attempts": 3, "max_attempts": 3, "payload": {},
    }])
    queue = FakeQueue()

    await process_opportunity("job-3", store, queue)

    assert store.updated[0][1] == "failed"
    assert "maximum attempts reached" in store.updated[0][2]["error_message"]
    assert queue.jobs == []
