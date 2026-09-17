import pytest

from app.services.reflection import ReflectionEngine


class FakeMemory:
    def __init__(self):
        self.candidates = []
        self.promoted = []

    async def record_candidate(self, category, statement, evidence, **kwargs):
        row = {"id": "m1", "category": category, "statement": statement, "status": "candidate"}
        self.candidates.append(row)
        return row

    async def promote(self, memory_id, *, evidence):
        row = {"id": memory_id, "status": "active", "evidence": evidence}
        self.promoted.append(row)
        return row


class FakeStore:
    async def list_events(self):
        return [{"event_type": "incident_resolved", "payload": {"cause": "timeout", "fix": "retry"}}]


@pytest.mark.asyncio
async def test_reflection_promotes_verified_incident_lesson():
    memory = FakeMemory()
    reflection = ReflectionEngine(FakeStore(), memory)
    result = await reflection.run_once(trigger_type="scheduled")
    assert result["promoted"] == 1
    assert memory.promoted[0]["status"] == "active"
