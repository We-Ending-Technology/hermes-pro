from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from backend.app.services.shopify import (
    normalize_shopify_domain,
    normalize_shopify_event,
    sanitize_shopify_payload,
    verify_shopify_signature,
)


def test_shopify_hmac_uses_raw_body_and_sha256():
    secret = "shopify-test-secret"
    raw = b'{"id":123,"currency":"BRL","total_price":"29.90"}'
    signature = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
    assert verify_shopify_signature(raw, secret, signature)
    assert not verify_shopify_signature(raw + b" ", secret, signature)
    assert not verify_shopify_signature(raw, secret, "")


def test_shopify_domain_normalization():
    assert normalize_shopify_domain("https://0200rp-kz.myshopify.com/") == "0200rp-kz.myshopify.com"


def test_normalizes_paid_order_and_sanitizes_customer_data():
    payload = {
        "id": 123,
        "financial_status": "paid",
        "currency": "BRL",
        "current_total_price": "29.90",
        "email": "buyer@example.com",
        "customer": {"email": "buyer@example.com", "phone": "11999999999"},
    }
    event = normalize_shopify_event("orders/paid", payload)
    assert event == {
        "event_type": "PURCHASE_APPROVED",
        "external_id": "orders/paid:123",
        "amount": 29.9,
        "currency": "BRL",
        "order_id": "123",
    }
    safe = sanitize_shopify_payload("orders/paid", payload, event, "hook-1")
    assert safe["amount"] == 29.9
    assert safe["currency"] == "BRL"
    assert "email" not in safe
    assert "customer" not in safe


def test_normalizes_successful_refund_transaction():
    payload = {
        "id": 900,
        "order_id": 123,
        "currency": "BRL",
        "transactions": [
            {"kind": "sale", "status": "success", "amount": "29.90", "currency": "BRL"},
            {"kind": "refund", "status": "success", "amount": "9.90", "currency": "BRL"},
            {"kind": "refund", "status": "pending", "amount": "2.00", "currency": "BRL"},
        ],
        "email": "buyer@example.com",
    }
    event = normalize_shopify_event("refunds/create", payload)
    assert event["event_type"] == "PURCHASE_REFUNDED"
    assert event["external_id"] == "refunds/create:123:900"
    assert event["amount"] == 9.9
    assert event["currency"] == "BRL"
    safe = sanitize_shopify_payload("refunds/create", payload, event)
    assert "email" not in safe


def test_unsupported_shopify_topics_are_ignored():
    assert normalize_shopify_event("products/update", {"id": 1}) is None


def test_invalid_or_missing_order_financial_data_is_rejected():
    with pytest.raises(ValueError, match="missing id"):
        normalize_shopify_event("orders/paid", {"total_price": "29.90", "currency": "BRL"})
    with pytest.raises(ValueError, match="successful refund transaction"):
        normalize_shopify_event("refunds/create", {"id": 1, "order_id": 2, "transactions": []})
