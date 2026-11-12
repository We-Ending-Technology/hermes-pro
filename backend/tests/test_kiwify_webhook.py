import hashlib
import hmac
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import api_commercial
from backend.app.db.supabase import SupabaseError


class IdempotentFakeStore:
    def __init__(self):
        self.events = {}

    async def append_event(
        self, provider, event_type, payload, external_id=None, amount=None, currency=None
    ):
        key = (provider, external_id)
        if key in self.events:
            raise SupabaseError("duplicate key value violates unique constraint (23505)")
        self.events[key] = {
            "event_type": event_type,
            "payload": payload,
            "amount": amount,
            "currency": currency,
        }
        return self.events[key]


def _client(monkeypatch):
    fake_store = IdempotentFakeStore()
    monkeypatch.setattr(
        api_commercial, "settings", SimpleNamespace(kiwify_webhook_token="test-secret")
    )
    monkeypatch.setattr(api_commercial, "store", fake_store)
    app = FastAPI()
    app.include_router(api_commercial.router)
    return TestClient(app), fake_store


def _signed_request(client, body, signature=None):
    signature = signature or hmac.new(
        b"test-secret", body, hashlib.sha1
    ).hexdigest()
    return client.post(
        f"/api/v1/webhooks/kiwify?signature={signature}",
        content=body,
        headers={"content-type": "application/json"},
    )


def test_kiwify_webhook_valid_signature_processes_event(monkeypatch):
    client, store = _client(monkeypatch)
    body = b'{"webhook_event_type":"order_approved","order_id":"order-123"}'

    response = _signed_request(client, body)

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["duplicate"] is False
    assert len(store.events) == 1
    assert ("kiwify", "order-123:order_approved") in store.events


def test_kiwify_webhook_invalid_signature_returns_401_without_processing(monkeypatch):
    client, store = _client(monkeypatch)
    body = b'{"webhook_event_type":"order_approved","order_id":"order-123"}'

    response = _signed_request(client, body, "0" * 40)

    assert response.status_code == 401
    assert store.events == {}


def test_kiwify_webhook_duplicate_event_is_ignored(monkeypatch):
    client, store = _client(monkeypatch)
    body = b'{"webhook_event_type":"order_approved","order_id":"order-123"}'

    first = _signed_request(client, body)
    second = _signed_request(client, body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert len(store.events) == 1


def test_kiwify_signature_requires_lowercase_hex():
    body = b'{"order_id":"order-123"}'
    signature = hmac.new(b"test-secret", body, hashlib.sha1).hexdigest().upper()

    assert api_commercial.verify_kiwify_signature(body, "test-secret", signature) is False
