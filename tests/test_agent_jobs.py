from types import SimpleNamespace

import pytest

from worker import agent_jobs
from worker.main import recover_pending


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
        self.recoverable_jobs = []

    async def list_recoverable_jobs(self, stale_before):
        return self.recoverable_jobs

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
    assert queue.enqueued == []


@pytest.mark.asyncio
async def test_chief_receives_live_operational_facts(monkeypatch):
    store = FakeStore()
    async def fake_select(table, params):
        return {
            "hermes_products": [
                {"id": "p1", "title": "Manual Python", "status": "review_required", "current_stage": "reviewer"}
            ],
            "hermes_jobs": [
                {"id": "j1", "job_type": "agent_run", "status": "failed", "attempts": 3, "error_message": "503"}
            ],
            "hermes_sales_events": [
                {"provider": "kiwify", "event_type": "PURCHASE_APPROVED", "amount": 49.9, "currency": "BRL"}
            ],
            "hermes_system_health": [
                {"component": "worker", "status": "ok", "message": "Redis PING succeeded"}
            ],
        }.get(table, [])
    store.db.select = fake_select
    captured = {}

    async def fake_run_chief(instruction, settings):
        captured["instruction"] = instruction
        return {"output": "Diagnóstico com evidências", "specialists": {}}

    monkeypatch.setattr(agent_jobs, "run_chief", fake_run_chief)
    settings = SimpleNamespace(ai_provider="gemini", ai_fallback_provider="openai", openai_api_key=None, gemini_model="gemini-test")
    await agent_jobs.process_agent("run-1", store, settings, FakeQueue())

    assert store.job["status"] == "completed"
    assert "Manual Python" in captured["instruction"]
    assert "review_required" in captured["instruction"]
    assert "PURCHASE_APPROVED" in captured["instruction"]
    assert "Redis PING succeeded" in captured["instruction"]
    saved = next(values for table, values, _ in store.db.updates if table == "hermes_agent_runs" and values.get("status") == "completed")
    assert saved["output"]["operational_context"]["sales"]["approved_purchase_events"] == 1


@pytest.mark.asyncio
async def test_persistent_recovery_requeues_retrying_agent_job():
    store, queue = FakeStore(), FakeQueue()
    store.recoverable_jobs = [{"id": "run-1", "job_type": "agent_run", "status": "retrying"}]
    await recover_pending(store, queue)
    assert queue.enqueued == ["run-1"]
