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
    def __init__(self, products=None, jobs=None):
        self.products = products or []
        self.jobs = jobs or []
        self.created = []
        self.rebuilds = []
        self.validations = []

    async def list_products(self):
        return self.products

    async def list_jobs(self):
        return self.jobs

    async def create_product_rebuild_job(self, product_id):
        index = next(i for i, item in enumerate(self.products) if str(item.get("id")) == str(product_id))
        product = self.products[index]
        metadata = dict(product.get("metadata") or {})
        attempt = int(metadata.get("rebuild_attempts") or 0) + 1
        metadata["rebuild_attempts"] = attempt
        metadata["artifact_status"] = "revision_required"
        metadata["publication_status"] = "not_published"
        quality_gate = dict(metadata.get("quality_gate") or {})
        quality_gate.update({"approved": False, "rebuild_pending": True})
        metadata["quality_gate"] = quality_gate
        updated = {**product, "status": "queued", "metadata": metadata}
        self.products[index] = updated
        job = {
            "id": f"rebuild-job-{len(self.rebuilds) + 1}",
            "job_type": "product_generation",
            "status": "pending",
            "payload": {"product_id": str(product_id), "topic": product.get("topic")},
        }
        self.jobs.append(job)
        self.rebuilds.append((str(product_id), attempt))
        return updated, job



    async def create_product_validation_job(self, product_id):
        index = next(i for i, item in enumerate(self.products) if str(item.get("id")) == str(product_id))
        product = self.products[index]
        metadata = dict(product.get("metadata") or {})
        attempt = int(metadata.get("validation_attempts") or 0) + 1
        metadata["validation_attempts"] = attempt
        metadata["artifact_status"] = "revision_required"
        updated = {**product, "status": "queued", "metadata": metadata}
        self.products[index] = updated
        job = {
            "id": f"validation-job-{len(self.validations) + 1}",
            "job_type": "product_generation",
            "status": "pending",
            "payload": {"product_id": str(product_id), "topic": product.get("topic"), "reuse_existing_content": True},
        }
        self.jobs.append(job)
        self.validations.append((str(product_id), attempt))
        return updated, job

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

    async def depths(self):
        return {"product": len(self.jobs), "agent": 0}


def test_json_object_accepts_markdown_fence():
    parsed = autonomy_scheduler._json_object(chr(96) * 3 + "json" + chr(10) + "{\"topic\":\"Tema válido\"}" + chr(10) + chr(96) * 3)
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

@pytest.mark.asyncio
async def test_review_required_product_is_rebuilt_before_new_product_discovery(monkeypatch):
    monkeypatch.setattr(autonomy_scheduler, "build_ai_gateway", lambda settings: FakeGateway())
    settings = Settings(
        autonomy_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        autonomy_max_daily_products=3,
        autonomy_max_active_products=5,
        autonomy_max_ready_to_publish=2,
        autonomy_max_review_required_products=3,
    )
    product = {
        "id": "p-1",
        "status": "review_required",
        "topic": "Ebook curto",
        "created_at": "2026-11-09T10:00:00Z",
        "metadata": {"artifact_status": "revision_required", "quality_gate": {"approved": False}},
    }
    store, queue = FakeStore([product]), FakeQueue()
    result = await autonomy_scheduler.autonomy_tick(settings, store, queue)
    assert result["status"] == "review_product_rebuild_queued"
    assert result["product_id"] == "p-1"
    assert store.rebuilds == [("p-1", 1)]
    assert store.products[0]["status"] == "queued"
    assert queue.jobs == ["rebuild-job-1"]


@pytest.mark.asyncio
async def test_review_backlog_rebuilds_oldest_product_first():
    settings = Settings(
        autonomy_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        autonomy_max_active_products=5,
        autonomy_max_ready_to_publish=2,
        autonomy_max_review_required_products=3,
    )
    products = [
        {"id": "newer", "status": "review_required", "topic": "Tema mais novo", "created_at": "2026-11-10T10:00:00Z", "metadata": {"artifact_status": "revision_required", "quality_gate": {"approved": False}}},
        {"id": "older", "status": "review_required", "topic": "Tema mais antigo", "created_at": "2026-11-08T10:00:00Z", "metadata": {"artifact_status": "revision_required", "quality_gate": {"approved": False}}},
    ]
    store, queue = FakeStore(products), FakeQueue()
    result = await autonomy_scheduler.autonomy_tick(settings, store, queue)
    assert result["status"] == "review_product_rebuild_queued"
    assert result["product_id"] == "older"
    assert queue.jobs == ["rebuild-job-1"]


@pytest.mark.asyncio
async def test_review_required_backlog_limit_applies_after_rebuild_attempts_are_exhausted():
    settings = Settings(
        autonomy_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        autonomy_max_active_products=5,
        autonomy_max_ready_to_publish=2,
        autonomy_max_review_required_products=3,
    )
    store = FakeStore([
        {
            "id": f"p-{i}",
            "status": "review_required",
            "topic": f"Tema {i}",
            "metadata": {
                "artifact_status": "revision_required",
                "quality_gate": {"approved": False},
                "rebuild_attempts": autonomy_scheduler.MAX_AUTOMATIC_REBUILDS_PER_PRODUCT,
            },
        }
        for i in range(4)
    ])
    queue = FakeQueue()
    result = await autonomy_scheduler.autonomy_tick(settings, store, queue)
    assert result == {"status": "review_backlog_full", "review_required": 4}
    assert store.rebuilds == []
    assert store.created == []
    assert queue.jobs == []

@pytest.mark.asyncio
async def test_failed_rebuild_product_gets_one_bounded_second_attempt():
    settings = Settings(
        autonomy_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        autonomy_max_active_products=5,
        autonomy_max_ready_to_publish=2,
        autonomy_max_review_required_products=3,
    )
    product = {
        "id": "p-failed",
        "status": "failed",
        "topic": "Guia digital com falha técnica",
        "metadata": {
            "artifact_status": "revision_required",
            "quality_gate": {"approved": False},
            "rebuild_attempts": 1,
        },
    }
    store, queue = FakeStore([product]), FakeQueue()
    result = await autonomy_scheduler.autonomy_tick(settings, store, queue)
    assert result["status"] == "review_product_rebuild_queued"
    assert result["attempt"] == 2
    assert store.rebuilds == [("p-failed", 2)]
    assert queue.jobs == ["rebuild-job-1"]


@pytest.mark.asyncio
async def test_content_that_passed_deterministic_gate_uses_validation_only_job():
    settings = Settings(
        autonomy_enabled=True,
        ai_provider="gemini",
        gemini_api_key="test-key",
        autonomy_max_active_products=5,
        autonomy_max_ready_to_publish=2,
        autonomy_max_review_required_products=3,
    )
    product = {
        "id": "p-metrics-pass",
        "status": "review_required",
        "topic": "Sistema de loja",
        "created_at": "2026-11-09T10:00:00Z",
        "metadata": {
            "artifact_status": "revision_required",
            "rebuild_attempts": 1,
            "quality_gate": {
                "approved": False,
                "findings": [],
                "word_count": 5668,
                "chapter_count": 8,
                "illustration_count": 4,
                "introduction_words": 314,
                "conclusion_words": 307,
                "chapter_word_counts": [{"title": f"Capítulo {i}", "words": 600} for i in range(8)],
            },
            "content_data": {"chapters": [{"title": f"Capítulo {i}", "content": "conteúdo"} for i in range(8)]},
            "review": {"approved": False, "score": 75, "findings": ["faltam páginas e ilustrações"]},
        },
    }
    store, queue = FakeStore([product]), FakeQueue()
    result = await autonomy_scheduler.autonomy_tick(settings, store, queue)
    assert result["status"] == "review_product_validation_queued"
    assert result["product_id"] == "p-metrics-pass"
    assert store.validations == [("p-metrics-pass", 1)]
    assert store.rebuilds == []
    assert queue.jobs == ["validation-job-1"]
