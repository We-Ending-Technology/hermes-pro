import pytest

from worker.autonomy_scheduler import recovery_probe_tick


class FakeStore:
    def __init__(self):
        self.job = {"id": "probe-1", "status": "pending"}
        self.calls = []

    async def create_agent_job(self, instruction, source, now, idempotency_key):
        self.calls.append({
            "instruction": instruction,
            "source": source,
            "now": now,
            "idempotency_key": idempotency_key,
        })
        return dict(self.job)


class FakeQueue:
    def __init__(self):
        self.enqueued = []

    async def enqueue_agent(self, job_id):
        self.enqueued.append(job_id)


@pytest.mark.asyncio
async def test_recovery_probe_is_idempotent_and_queues_only_nonterminal_job():
    store, queue = FakeStore(), FakeQueue()

    first = await recovery_probe_tick(store, queue)
    assert first["status"] == "probe_queued"
    assert first["ai_calls"] == 0
    assert queue.enqueued == ["probe-1"]
    assert store.calls[0]["source"] == "system_recovery_probe"
    assert store.calls[0]["idempotency_key"].startswith("system-recovery-probe:")

    store.job["status"] = "completed"
    second = await recovery_probe_tick(store, queue)
    assert second["status"] == "already_completed"
    assert queue.enqueued == ["probe-1"]
