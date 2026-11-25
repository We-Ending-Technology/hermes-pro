import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, settings
from backend.app import main as main_module


@pytest.fixture(autouse=True)
def configure_test_ai_budget(monkeypatch):
    async def allow_test_budget():
        return {
            "allowed": True,
            "reason": "test_budget",
            "daily_ai_budget": "10",
            "daily_total_budget": "10",
        }
    monkeypatch.setattr(main_module, "_require_ai_budget", allow_test_budget)
    monkeypatch.setattr(main_module.settings, "hermes_api_key", "test-hermes-key")


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_private_api_requires_server_side_key():
    with TestClient(app) as client:
        missing = client.get("/api/v1/agents")
        invalid = client.get("/api/v1/agents", headers={"X-Hermes-API-Key": "wrong-key"})
        authorized = client.get("/api/v1/agents", headers={"X-Hermes-API-Key": "test-hermes-key"})

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert authorized.status_code == 200


def test_private_api_fails_closed_without_server_secret(monkeypatch):
    monkeypatch.setattr(main_module.settings, "hermes_api_key", None)
    with TestClient(app) as client:
        response = client.get("/api/v1/agents")

    assert response.status_code == 503


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


def test_health_does_not_require_manual_api_key():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

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

def test_shopify_webhook_verifies_signature_and_store_before_recording(monkeypatch):
    import base64
    import hashlib
    import hmac
    import json
    from unittest.mock import AsyncMock
    from backend.app import api_commercial

    secret = "shopify-test-secret"
    domain = "0200rp-kz.myshopify.com"
    monkeypatch.setattr(api_commercial.settings, "shopify_webhook_secret", secret)
    monkeypatch.setattr(api_commercial.settings, "shopify_store_domain", domain)
    append_event = AsyncMock(return_value={})
    monkeypatch.setattr(api_commercial.store, "append_event", append_event)

    payload = {
        "id": 123,
        "currency": "BRL",
        "current_total_price": "29.90",
        "email": "buyer@example.com",
        "customer": {"email": "buyer@example.com"},
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Hmac-Sha256": signature,
        "X-Shopify-Topic": "orders/paid",
        "X-Shopify-Webhook-Id": "hook-123",
        "X-Shopify-Shop-Domain": domain,
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/webhooks/shopify", content=raw, headers=headers)
        invalid_signature = client.post(
            "/api/v1/webhooks/shopify",
            content=raw,
            headers={**headers, "X-Shopify-Hmac-Sha256": "invalid"},
        )
        wrong_store = client.post(
            "/api/v1/webhooks/shopify",
            content=raw,
            headers={**headers, "X-Shopify-Shop-Domain": "other.myshopify.com"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "duplicate": False, "event": "PURCHASE_APPROVED"}
    assert invalid_signature.status_code == 401
    assert wrong_store.status_code == 403
    append_event.assert_awaited_once()
    saved_payload = append_event.await_args.args[2]
    assert "email" not in saved_payload
    assert "customer" not in saved_payload
    assert append_event.await_args.args[:2] == ("shopify", "PURCHASE_APPROVED")


def test_shopify_webhook_is_public_but_requires_configuration(monkeypatch):
    from backend.app import api_commercial

    monkeypatch.setattr(api_commercial.settings, "shopify_webhook_secret", None)
    monkeypatch.setattr(api_commercial.settings, "shopify_store_domain", None)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/webhooks/shopify",
            content=b"{}",
            headers={"X-Shopify-Hmac-Sha256": "x"},
        )
    assert response.status_code == 503



def test_paused_product_does_not_refresh_missing_artifact_urls(monkeypatch):
    import asyncio
    from datetime import datetime, timezone
    from backend.app import main as main_module

    artifact_paths = {
        "pdf": {
            "bucket": "ebooks",
            "path": "old-paused-product/ebook.pdf",
        }
    }
    row = {
        "id": "old-paused-product",
        "topic": "produto pausado",
        "title": "Produto pausado",
        "status": "paused",
        "current_stage": "create_outline",
        "metadata": {
            "artifact_paths": artifact_paths,
            "artifact_urls_expires_at": "2026-01-01T00:00:00Z",
        },
        "created_at": datetime.now(timezone.utc),
    }

    def unexpected_storage_call(*args, **kwargs):
        pytest.fail("paused products must not attempt to refresh missing storage objects")

    monkeypatch.setattr(main_module, "SupabaseStorage", unexpected_storage_call)
    response = asyncio.run(main_module.product_response(row))

    assert response.status == "paused"
    assert response.metadata["artifact_paths"] == artifact_paths
