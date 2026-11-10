from types import SimpleNamespace

import pytest

from worker import agent_jobs

class FakeDB:
    def __init__(self):
        self.updates = []

    async def update(self, table, values, *, where):
        self.updates.append((table, values, where))
        return {"id": where["id"].removeprefix("eq.")}

class FakeStore:
    def __init__(self):
        self.job = {"id": "run-1", "job_type": "agent_run", "status": "pending", "attempts": 0, "max_attempts": 3, "payload": {"instruction": "Audite a fila"}}
        self.db = FakeDB()

    async def get_job(self, job_id):
        return self.job

    async def update_job(self, job_id, status, *, attempts=None, error_message=None):
        self.job.update(status=status, error_message=error_message)
        if attempts is not None:
            self.job["attempts"] = attempts
        return self.job

class FakeQueue:
    def __init__(self):
        self.enqueued = []

    async def enqueue_agent(self, job_id):
        self.enqueued.append(job_id)

@pytest.mark.asyncio
async def test_agent_job_persists_completed_result(monkeypatch):
    async def fake_run_chief(instruction, settings):
        return {"output": "Auditoria concluida", "specialists": {"Hermes Dev": "OK"}}

    monkeypatch.setattr(agent_jobs, "run_chief", fake_run_chief)
    store, queue = FakeStore(), FakeQueue()
    await agent_jobs.process_agent("run-1", store, SimpleNamespace(), queue)
    assert store.job["status"] == "completed"
    assert store.job["attempts"] == 1
    assert any(table == "hermes_agent_runs" and values["status"] == "completed" for table, values, _ in store.db.updates)
    assert queue.enqueued == []

@pytest.mark.asyncio
async def test_agent_job_retries_and_remains_recoverable(monkeypatch):
    async def fake_run_chief(instruction, settings):
        raise RuntimeError("temporary provider failure")

    monkeypatch.setattr(agent_jobs, "run_chief", fake_run_chief)
    store, queue = FakeStore(), FakeQueue()
    await agent_jobs.process_agent("run-1", store, SimpleNamespace(), queue)
    assert store.job["status"] == "retrying"
    assert store.job["attempts"] == 1
    assert queue.enqueued == []  # persistent recovery scan retries after the backoff window