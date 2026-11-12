from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.app.services import sentinel


class FakeResponse:
    status_code = 200
    @property
    def is_success(self):
        return True


class FakeClient:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def get(self, url):
        return FakeResponse()


class FakeDB:
    def __init__(self, worker_checked_at):
        self.worker_checked_at = worker_checked_at
        self.inserts = []
        self.updates = []
    async def health(self):
        return True
    async def select(self, table, params):
        if table == "hermes_system_health":
            return [{"status": "ok", "checked_at": self.worker_checked_at, "message": "worker"}]
        return []
    async def insert(self, table, values):
        self.inserts.append((table, values))
        return values
    async def update(self, table, values, where):
        self.updates.append((table, values, where))
        return values


class FakeStore:
    def __init__(self, db):
        self.db = db
    async def list_recoverable_jobs(self, stale_before):
        return []
    async def record_worker_health(self, *args):
        pass


class FakeRedis:
    async def ping(self):
        return True


class FakeQueue:
    def __init__(self):
        self.redis = FakeRedis()
    async def depths(self):
        return {"product": 0, "agent": 0}


@pytest.mark.asyncio
async def test_sentinel_reports_healthy_dependencies(monkeypatch):
    monkeypatch.setattr(sentinel.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    db = FakeDB(datetime.now(timezone.utc).isoformat())
    result = await sentinel.sentinel_tick(
        type("Settings", (), {"hermes_public_api_url": "https://api.example.test", "telegram_bot_token": None, "telegram_chat_id": None})(),
        FakeStore(db),
        FakeQueue(),
    )
    assert result["status"] == "healthy"
    assert all(result["checks"].values())


@pytest.mark.asyncio
async def test_sentinel_detects_stale_worker_and_persists_incident(monkeypatch):
    monkeypatch.setattr(sentinel.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    stale = (datetime.now(timezone.utc) - timedelta(seconds=105)).isoformat()
    db = FakeDB(stale)
    result = await sentinel.sentinel_tick(
        type("Settings", (), {"hermes_public_api_url": "https://api.example.test", "telegram_bot_token": None, "telegram_chat_id": None})(),
        FakeStore(db),
        FakeQueue(),
    )
    assert result["status"] == "degraded"
    assert result["checks"]["worker"] is False
    assert any(table == "hermes_incidents" for table, _ in db.inserts)
