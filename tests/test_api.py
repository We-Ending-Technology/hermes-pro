import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, settings


@pytest.fixture(autouse=True)
def configure_test_api_key(monkeypatch):
    monkeypatch.setattr(settings, "hermes_api_key", "test-hermes-key")


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_diagnostic_agent() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/run",
            json={"agent": "diagnostic", "input": {"prompt": "hello"}},
            headers={"X-Hermes-API-Key": "test-hermes-key"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["output"]["provider"] == "stub"


def test_unknown_agent() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/run",
            json={"agent": "unknown", "input": {}},
            headers={"X-Hermes-API-Key": "test-hermes-key"},
        )
    assert response.status_code == 404



def test_kiwify_webhook_requires_official_hmac_signature(monkeypatch):
    import hashlib
    import hmac
    import json
    from unittest.mock import AsyncMock
    from backend.app import api_commercial

    monkeypatch.setattr(api_commercial.settings, "kiwify_webhook_token", "kiwify-token-de-teste")
    append_event = AsyncMock()
    monkeypatch.setattr(api_commercial.store, "append_event", append_event)
    payload = {
        "order_id": "9b1c2d3e-0000-4000-8000-000000000001",
        "order_status": "paid",
        "webhook_event_type": "order_approved",
        "Commissions": {"charge_amount": 5000, "currency": "BRL"},
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(b"kiwify-token-de-teste", raw, hashlib.sha1).hexdigest()

    with TestClient(app) as client:
        response = client.post("/api/v1/webhooks/kiwify?signature=" + signature, content=raw, headers={"Content-Type": "application/json"})
        invalid = client.post("/api/v1/webhooks/kiwify?signature=" + "0" * 40, content=raw, headers={"Content-Type": "application/json"})

    assert response.status_code == 200
    assert response.json()["event"] == "PURCHASE_APPROVED"
    assert invalid.status_code == 401
    append_event.assert_awaited_once()


def test_unicode_api_key_header_returns_401_not_internal_server_error():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/dashboard",
            headers=[(b"X-Hermes-API-Key", b"chave-\xff-invalida")],
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Acesso privado: chave inválida ou ausente."

def test_ai_provider_key_configured_recognizes_groq_fallback():
    from backend.app.api_commercial import _ai_provider_key_configured
    from backend.app.core.config import Settings

    assert _ai_provider_key_configured("groq", Settings(groq_api_key="test-groq-key"))
    assert not _ai_provider_key_configured("groq", Settings())
    assert _ai_provider_key_configured("gemini", Settings(gemini_api_key="test-gemini-key"))

def test_manual_factory_request_creates_product_without_fabricating_market_validation(monkeypatch):
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock
    from backend.app import main as main_module

    product_id = "2d04a4c1-3b7a-4590-8a96-d158c1a12f27"
    job_id = "7c9f1cd0-5fe4-49b7-b1eb-12bcc3dcf072"
    product = {
        "id": product_id,
        "topic": "guia prático de organização financeira",
        "title": None,
        "status": "queued",
        "current_stage": "create_outline",
        "metadata": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    job = {"id": job_id}
    select = AsyncMock(return_value=[])
    create = AsyncMock(side_effect=lambda topic, metadata, idempotency_key: ({**product, "metadata": metadata}, job))
    enqueue = AsyncMock()
    monkeypatch.setattr(main_module.db, "select", select)
    monkeypatch.setattr(main_module.store, "create_product_and_job", create)
    monkeypatch.setattr(main_module.queue, "enqueue", enqueue)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/products",
            json={
                "topic": "guia prático de organização financeira",
                "metadata": {"manual_market_override": True},
            },
            headers={"X-Hermes-API-Key": "test-hermes-key"},
        )

    assert response.status_code == 202
    assert response.json()["metadata"]["market_validation"]["status"] == "manual_override"
    assert "não foi validada" in response.json()["metadata"]["market_validation"]["reason"]
    select.assert_not_awaited()
    create.assert_awaited_once()
    enqueue.assert_awaited_once_with(job_id)


def test_automatic_factory_request_still_requires_positive_market_signal(monkeypatch):
    from unittest.mock import AsyncMock
    from backend.app import main as main_module

    select = AsyncMock(return_value=[])
    create = AsyncMock()
    monkeypatch.setattr(main_module.db, "select", select)
    monkeypatch.setattr(main_module.store, "create_product_and_job", create)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/products",
            json={"topic": "nicho sem evidência positiva"},
            headers={"X-Hermes-API-Key": "test-hermes-key"},
        )

    assert response.status_code == 409
    create.assert_not_awaited()

