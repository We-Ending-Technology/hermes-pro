from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.core.config import Settings
from worker import autonomy_scheduler


class FakeGateway:
    async def complete(self, prompt: str, *, system: str | None = None):
        return SimpleNamespace(
            content='{"topic":"Organização financeira doméstica para autônomos","rationale":"Guia prático de organização cotidiana","target_audience":"Autônomos brasileiros","differentiator":"Modelos preenchíveis"}',
            provider="test",
            model="test-model",
        )


class FakeStore:
    def __init__(self, products=None):
        self.products = products or []
        self.created = []

    async def list_products(self):
        return self.products

    async def create_product_and_job(self, topic, metadata, idempotency_key):
        product = {"id": "product-1", "topic": topic}
        job = {"id": "job-1"}
        self.created.append((product, job, metadata, idempotency_key))
        return product, job


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, job_id):
        self.jobs.append(job_id)


def test_json_object_accepts_markdown_fence():
    parsed = autonomy_scheduler._json_object(chr(96) * 3 + "json\\n{\"topic\":\"Tema válido\"}\\n" + chr(96) * 3)
    assert parsed["topic"] == "Tema válido"


@pytest.mark.asyncio
async def test_autonomy_tick_queues_a_real_product(monkeypatch):
    monkeypatch.setattr(autonomy_scheduler, "build_ai_gateway", lambda settings: FakeGateway())
    settings = Settings(
        autonomy_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        autonomy_max_daily_products=3,
        autonomy_max_active_products=1,
        autonomy_max_ready_to_publish=2,
    )
    store, queue = FakeStore(), FakeQueue()

    result = await autonomy_scheduler.autonomy_tick(settings, store, queue)

    assert result["status"] == "product_queued"
    assert store.created[0][0]["topic"] == "Organização financeira doméstica para autônomos"
    assert store.created[0][2]["market_validation"] == "not_yet_verified"
    assert queue.jobs == ["job-1"]


@pytest.mark.asyncio
async def test_autonomy_tick_stops_when_active_capacity_is_full(monkeypatch):
    monkeypatch.setattr(autonomy_scheduler, "build_ai_gateway", lambda settings: FakeGateway())
    settings = Settings(
        autonomy_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        autonomy_max_active_products=1,
    )
    store = FakeStore([{"id": "existing", "status": "generating", "created_at": datetime.now(timezone.utc).isoformat()}])
    queue = FakeQueue()

    result = await autonomy_scheduler.autonomy_tick(settings, store, queue)

    assert result["status"] == "capacity_full"
    assert store.created == []
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_autonomy_tick_stops_when_daily_limit_is_reached(monkeypatch):
    monkeypatch.setattr(autonomy_scheduler, "build_ai_gateway", lambda settings: FakeGateway())
    settings = Settings(
        autonomy_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        autonomy_max_daily_products=1,
        autonomy_max_active_products=2,
        autonomy_max_ready_to_publish=2,
    )
    store = FakeStore([{"id": "existing", "status": "failed", "created_at": datetime.now(timezone.utc).isoformat()}])
    queue = FakeQueue()

    result = await autonomy_scheduler.autonomy_tick(settings, store, queue)

    assert result["status"] == "daily_limit_reached"
    assert store.created == []
    assert queue.jobs == []
