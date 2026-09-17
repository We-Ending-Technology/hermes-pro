import pytest

from app.services.watchdog import WatchdogEngine


class FakeStore:
    def __init__(self):
        self.jobs = [{"id": "j1", "status": "running", "updated_at": "2000-01-01T00:00:00+00:00", "attempts": 0, "max_attempts": 3}]
        self.incidents = {}

    async def list_jobs(self):
        return self.jobs

    async def upsert_incident(self, fingerprint, values):
        row = self.incidents.setdefault(fingerprint, {"id": "i1", "attempts": 0})
        row.update(values)
        row["attempts"] = row.get("attempts", 0) + 1
        return row


@pytest.mark.asyncio
async def test_stalled_job_creates_one_deduplicated_incident():
    store = FakeStore()
    watchdog = WatchdogEngine(store, stale_after_seconds=60)
    first = await watchdog.run_once(now="2026-09-17T12:00:00+00:00")
    second = await watchdog.run_once(now="2026-09-17T12:01:00+00:00")
    assert first["incidents"] == 1
    assert second["incidents"] == 1
    assert len(store.incidents) == 1
