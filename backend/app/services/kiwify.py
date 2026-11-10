from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_kiwify_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Kiwify's documented product webhook into Hermes sales events."""
    order_id = payload.get("order_id") or payload.get("order_ref")
    if not order_id:
        raise ValueError("Kiwify event is missing order_id/order_ref")

    raw_event = str(payload.get("webhook_event_type") or payload.get("event") or "").strip().lower()
    raw_status = str(payload.get("order_status") or "").strip().lower()
    combined = f"{raw_event} {raw_status}"

    if any(term in combined for term in ("chargeback", "charge_back", "contestacao", "contestação")):
        event_type = "PURCHASE_CHARGEBACK"
    elif any(term in combined for term in ("refund", "refunded", "reembolso", "reembolsado")):
        event_type = "PURCHASE_REFUNDED"
    elif "subscription" in combined and any(term in combined for term in ("renew", "renov", "paid")):
        event_type = "SUBSCRIPTION_RENEWED"
    elif raw_status in {"paid", "approved", "complete", "completed"} or any(
        term in raw_event for term in ("order_approved", "purchase_approved", "order_paid")
    ):
        event_type = "PURCHASE_APPROVED"
    elif any(term in combined for term in ("cancel", "canceled", "cancelled")):
        event_type = "PURCHASE_CANCELLED"
    elif any(term in combined for term in ("waiting", "pending", "pix_generated", "boleto_generated")):
        event_type = "PAYMENT_PENDING"
    else:
        event_type = "OTHER"

    commissions = payload.get("Commissions") or payload.get("commissions") or {}
    raw_amount = commissions.get("charge_amount")
    if raw_amount is None:
        raw_amount = commissions.get("product_base_price")
    amount = None
    if raw_amount is not None:
        try:
            amount = float((Decimal(str(raw_amount)).copy_abs() / Decimal("100")).quantize(Decimal("0.01")))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Kiwify Commissions amount is invalid")

    return {
        "event_type": event_type,
        "external_id": f"{order_id}:{event_type.lower()}",
        "amount": amount,
        "currency": str(commissions.get("currency") or commissions.get("product_base_price_currency") or "BRL").upper(),
    }


def sanitize_kiwify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep sales metadata without storing buyer PII or course-access URLs."""
    safe = dict(payload)
    safe.pop("Customer", None)
    safe.pop("customer", None)
    safe.pop("access_url", None)
    commissions = safe.get("Commissions") or safe.get("commissions")
    if isinstance(commissions, dict):
        commissions = dict(commissions)
        stores = commissions.get("commissioned_stores")
        if isinstance(stores, list):
            commissions["commissioned_stores"] = [
                {key: value for key, value in item.items() if key.lower() != "email"}
                if isinstance(item, dict) else item
                for item in stores
            ]
        if "Commissions" in safe:
            safe["Commissions"] = commissions
        else:
            safe["commissions"] = commissions
    return safe



def verify_kiwify_signature(raw_body: bytes, token: str, signature: str) -> bool:
    """Verify Kiwify HMAC-SHA1 over the exact raw request body."""
    if not token or len(signature) != 40:
        return False
    expected = hmac.new(token.encode("utf-8"), raw_body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(expected, signature.lower())
