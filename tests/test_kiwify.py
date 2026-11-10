from backend.app.services.kiwify import normalize_kiwify_event, sanitize_kiwify_payload, verify_kiwify_signature


def test_normalizes_approved_order_from_cents():
    event = normalize_kiwify_event({
        "order_id": "order-123",
        "order_status": "paid",
        "webhook_event_type": "order_approved",
        "Commissions": {"charge_amount": 12424, "currency": "BRL"},
    })
    assert event == {
        "event_type": "PURCHASE_APPROVED",
        "external_id": "order-123:purchase_approved",
        "amount": 124.24,
        "currency": "BRL",
    }


def test_refund_and_chargeback_are_separate_idempotent_events():
    base = {"order_id": "order-123", "Commissions": {"charge_amount": 9900}}
    refund = normalize_kiwify_event({**base, "webhook_event_type": "order_refunded"})
    chargeback = normalize_kiwify_event({**base, "webhook_event_type": "order_chargeback"})
    assert refund["event_type"] == "PURCHASE_REFUNDED"
    assert chargeback["event_type"] == "PURCHASE_CHARGEBACK"
    assert refund["external_id"] != chargeback["external_id"]


def test_sanitizer_removes_buyer_data_and_access_url():
    safe = sanitize_kiwify_payload({
        "order_id": "order-123",
        "Customer": {"email": "buyer@example.com", "CPF": "123"},
        "access_url": "https://example.com/secret",
        "Commissions": {"commissioned_stores": [{"email": "partner@example.com", "value": "100"}]},
    })
    assert "Customer" not in safe
    assert "access_url" not in safe
    assert "email" not in safe["Commissions"]["commissioned_stores"][0]


def test_requires_stable_order_identifier():
    try:
        normalize_kiwify_event({"order_status": "paid"})
    except ValueError as exc:
        assert "order_id" in str(exc)
    else:
        raise AssertionError("expected missing order id to be rejected")



def test_verifies_official_kiwify_hmac_sha1_vector():
    token = "kiwify-token-de-teste"
    body = b'{"order_id":"9b1c2d3e-0000-4000-8000-000000000001","order_status":"paid","webhook_event_type":"order_approved"}'
    signature = "bf18f352a4f981b91dfa3f6d8742a81080ab8c86"
    assert verify_kiwify_signature(body, token, signature)


def test_rejects_modified_body_or_missing_signature():
    token = "kiwify-token-de-teste"
    signature = "bf18f352a4f981b91dfa3f6d8742a81080ab8c86"
    assert verify_kiwify_signature(b'{"order_id":"changed"}', token, signature) is False
    assert verify_kiwify_signature(b'{}', token, "") is False
