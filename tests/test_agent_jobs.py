from types import SimpleNamespace

import pytest

from worker import agent_jobs
from worker.main import recover_pending


class FakeDB:
    def __init__(self):
        self.updates = []
        self.memory = {}

    async def update(self, table, values, *, where):
        self.updates.append((table, values, where))
        return {"id": where["id"].removeprefix("eq.")}

    async def select(self, table, params):
        if table == "hermes_settings":
            return [{
                "kill_switch": False,
                "daily_ai_budget": "10",
                "daily_total_budget": "10",
            }]
        if table != "hermes_agent_memory":
            return []
        key = str(params.get("key") or "").removeprefix("eq.")
        if key:
            value = self.memory.get(key)
            return [{"value": value["value"]}] if value else []
        if params.get("source") == "eq.worker_recovery":
            return list(self.memory.values())[: int(params.get("limit", 8))]
        return []

    async def upsert(self, table, values, *, conflict):
        assert table == "hermes_agent_memory"
        assert conflict == "key"
        self.memory[values["key"]] = dict(values)
        return dict(values)


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
            "hermes_settings": [
                {
                    "kill_switch": False,
                    "daily_ai_budget": "10",
                    "daily_total_budget": "10",
                }
            ],
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
            "hermes_agent_memory": [
                {"key": "worker_recovery:transient_provider:test", "value": {"category": "transient_provider", "last_outcome": "recovered"}, "updated_at": "2026-11-23T00:00:00Z"}
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
    assert "transient_provider" in captured["instruction"]
    saved = next(values for table, values, _ in store.db.updates if table == "hermes_agent_runs" and values.get("status") == "completed")
    assert saved["output"]["operational_context"]["sales"]["approved_purchase_events"] == 1


@pytest.mark.asyncio
async def test_persistent_recovery_requeues_retrying_agent_job():
    store, queue = FakeStore(), FakeQueue()
    store.recoverable_jobs = [{"id": "run-1", "job_type": "agent_run", "status": "retrying"}]
    await recover_pending(store, queue)
    assert queue.enqueued == ["run-1"]


@pytest.mark.asyncio
async def test_agent_job_persists_failure_learning_then_marks_it_recovered(monkeypatch):
    calls = {"count": 0}

    async def fail_then_succeed(instruction, settings):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Gemini HTTP 503 temporarily unavailable")
        return {"output": "Tarefa concluída após recuperação", "specialists": {}}

    monkeypatch.setattr(agent_jobs, "run_chief", fail_then_succeed)
    store, queue = FakeStore(), FakeQueue()

    await agent_jobs.process_agent("run-1", store, SimpleNamespace(), queue)
    assert store.job["status"] == "retrying"
    assert len(store.db.memory) == 1
    key, record = next(iter(store.db.memory.items()))
    assert record["value"]["category"] == "transient_provider"
    assert record["value"]["last_outcome"] == "retry_scheduled"

    store.job["status"] = "pending"
    await agent_jobs.process_agent("run-1", store, SimpleNamespace(), queue)

    assert store.job["status"] == "completed"
    assert calls["count"] == 2
    learned = store.db.memory[key]["value"]
    assert learned["last_outcome"] == "recovered"
    assert learned["successful_job_id"] == "run-1"
    assert learned["successful_attempt"] == 2


@pytest.mark.asyncio
async def test_agent_job_does_not_retry_permanent_model_configuration_failure(monkeypatch):
    async def fail_configuration(instruction, settings):
        raise RuntimeError("Gemini HTTP 404 model not found")

    monkeypatch.setattr(agent_jobs, "run_chief", fail_configuration)
    store, queue = FakeStore(), FakeQueue()

    await agent_jobs.process_agent("run-1", store, SimpleNamespace(), queue)

    assert store.job["status"] == "failed"
    assert store.job["attempts"] == 1
    assert queue.enqueued == []
    learned = next(iter(store.db.memory.values()))["value"]
    assert learned["category"] == "configuration"
    assert learned["retryable"] is False
    assert learned["last_outcome"] == "needs_review"


@pytest.mark.asyncio
async def test_deterministic_recovery_probe_runs_without_ai_and_closes_learning_loop(monkeypatch):
    async def ai_must_not_run(instruction, settings):
        raise AssertionError("recovery probe must not call an AI provider")

    monkeypatch.setattr(agent_jobs, "run_chief", ai_must_not_run)
    store, queue = FakeStore(), FakeQueue()
    store.job["payload"]["source"] = "system_recovery_probe"

    await agent_jobs.process_agent("run-1", store, SimpleNamespace(), queue)
    assert store.job["status"] == "retrying"
    key, record = next(iter(store.db.memory.items()))
    assert record["value"]["category"] == "transient_provider"
    assert record["value"]["last_outcome"] == "retry_scheduled"

    store.job["status"] = "pending"
    await agent_jobs.process_agent("run-1", store, SimpleNamespace(), queue)

    assert store.job["status"] == "completed"
    saved = next(values for table, values, _ in store.db.updates if table == "hermes_agent_runs" and values.get("status") == "completed")
    assert saved["output"]["model_calls"] == 0
    assert saved["output"]["recovery_probe"]["successful_attempt"] == 2
    assert store.db.memory[key]["value"]["last_outcome"] == "recovered"
