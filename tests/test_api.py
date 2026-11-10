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
            headers={"X-Hermes-API-Key": "chave-ação-inválida"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Acesso privado: chave inválida ou ausente."
