import pytest

from app.services.memory import MemoryEngine


class FakeDB:
    def __init__(self):
        self.rows = []

    async def insert(self, table, values):
        row = dict(values)
        row.setdefault("id", str(len(self.rows) + 1))
        self.rows.append(row)
        return row

    async def select(self, table, *, params=None):
        params = params or {}
        rows = list(self.rows)
        status = params.get("status")
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return rows

    async def update(self, table, values, *, where):
        row = self.rows[0]
        row.update(values)
        return row


@pytest.mark.asyncio
async def test_candidate_lesson_is_promoted_only_with_evidence():
    db = FakeDB()
    memory = MemoryEngine(db)
    candidate = await memory.record_candidate("provider", "Gemini 503 recovers with configured failover", {"incident": "i1"})
    assert candidate["status"] == "candidate"
    promoted = await memory.promote(candidate["id"], evidence={"verified": True})
    assert promoted["status"] == "active"


@pytest.mark.asyncio
async def test_retrieval_excludes_rejected_lessons():
    db = FakeDB()
    memory = MemoryEngine(db)
    await memory.record_candidate("provider", "bad lesson", {})
    db.rows[0]["status"] = "rejected"
    results = await memory.retrieve("provider")
    assert results == []
