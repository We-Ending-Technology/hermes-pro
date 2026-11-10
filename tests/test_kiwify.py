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


def test_normalizes_documented_kiwify_rejected_and_pending_events():
    base = {"order_id": "order-789"}
    refused = normalize_kiwify_event({**base, "webhook_event_type": "order_rejected", "order_status": "refused"})
    pix = normalize_kiwify_event({**base, "webhook_event_type": "pix_created", "order_status": "waiting_payment"})
    billet = normalize_kiwify_event({**base, "webhook_event_type": "billet_created", "order_status": "waiting_payment"})
    assert refused["event_type"] == "PURCHASE_REFUSED"
    assert pix["event_type"] == "PAYMENT_PENDING"
    assert billet["event_type"] == "PAYMENT_PENDING"


def test_normalizes_documented_kiwify_subscription_lifecycle():
    base = {"subscription_id": "sub-123", "Commissions": {"charge_amount": 2500}}
    trial = normalize_kiwify_event({**base, "webhook_event_type": "subscription_trial_started", "order_status": "trial"})
    trial_cancel = normalize_kiwify_event({**base, "webhook_event_type": "subscription_trial_canceled", "order_status": "canceled"})
    renewed = normalize_kiwify_event({**base, "webhook_event_type": "subscription_renewed", "order_status": "paid", "order_id": "order-renew"})
    late = normalize_kiwify_event({**base, "webhook_event_type": "subscription_late", "order_status": "waiting_payment", "order_id": "order-late"})
    cancelled = normalize_kiwify_event({**base, "webhook_event_type": "subscription_canceled", "order_status": "paid", "order_id": "order-cancel"})
    assert trial["event_type"] == "SUBSCRIPTION_TRIAL_STARTED"
    assert trial_cancel["event_type"] == "SUBSCRIPTION_TRIAL_CANCELLED"
    assert renewed["event_type"] == "SUBSCRIPTION_RENEWED"
    assert late["event_type"] == "SUBSCRIPTION_LATE"
    assert cancelled["event_type"] == "SUBSCRIPTION_CANCELLED"


def test_kiwify_chargeback_accepts_documented_chargedback_status():
    event = normalize_kiwify_event({"order_id": "order-999", "order_status": "chargedback"})
    assert event["event_type"] == "PURCHASE_CHARGEBACK"
