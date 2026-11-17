from __future__ import annotations

import base64
import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_shopify_domain(value: str | None) -> str:
    """Normalize a Shopify domain for strict webhook-origin comparison."""
    domain = str(value or "").strip().lower()
    if domain.startswith("https://"):
        domain = domain[len("https://"):]
    elif domain.startswith("http://"):
        domain = domain[len("http://"):]
    return domain.rstrip("/")


def verify_shopify_signature(raw_body: bytes, secret: str, signature: str) -> bool:
    """Verify X-Shopify-Hmac-Sha256 against the exact raw request body."""
    if not secret or not signature:
        return False
    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("ascii")
    return hmac.compare_digest(expected, signature.strip())


def _decimal_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Shopify event amount is invalid") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Shopify event amount must be a finite non-negative value")
    return amount.quantize(Decimal("0.01"))


def _money_from_set(value: Any) -> tuple[Any, str | None] | None:
    if not isinstance(value, dict):
        return None
    money = value.get("shop_money") or value.get("presentment_money")
    if not isinstance(money, dict) or money.get("amount") is None:
        return None
    currency = money.get("currency_code") or money.get("currency")
    return money["amount"], str(currency).upper() if currency else None


def _order_amount(payload: dict[str, Any]) -> tuple[Decimal, str]:
    for key in ("current_total_price_set", "total_price_set"):
        money = _money_from_set(payload.get(key))
        if money:
            raw_amount, currency = money
            if currency:
                return _decimal_amount(raw_amount), currency
    raw_amount = payload.get("current_total_price")
    if raw_amount is None:
        raw_amount = payload.get("total_price")
    currency = payload.get("currency") or payload.get("presentment_currency")
    if raw_amount is None or not currency:
        raise ValueError("Shopify paid order is missing amount or currency")
    return _decimal_amount(raw_amount), str(currency).upper()


def _refund_amount(payload: dict[str, Any]) -> tuple[Decimal, str]:
    total = Decimal("0.00")
    currency: str | None = None
    transactions = payload.get("transactions") or []
    for transaction in transactions:
        if not isinstance(transaction, dict):
            continue
        if str(transaction.get("kind") or "").lower() != "refund":
            continue
        if str(transaction.get("status") or "").lower() not in {"success", "succeeded"}:
            continue
        money = _money_from_set(transaction.get("amount_set"))
        raw_amount, transaction_currency = money if money else (
            transaction.get("amount"),
            transaction.get("currency") or payload.get("currency"),
        )
        if raw_amount is None or not transaction_currency:
            continue
        transaction_currency = str(transaction_currency).upper()
        if currency and transaction_currency != currency:
            raise ValueError("Shopify refund contains mixed currencies")
        currency = transaction_currency
        total += _decimal_amount(raw_amount)
    if currency is None or total <= 0:
        raise ValueError("Shopify refund has no successful refund transaction")
    return total.quantize(Decimal("0.01")), currency


def normalize_shopify_event(topic: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Convert supported Shopify topics into Hermes sale events; ignore all other topics."""
    topic = str(topic or "").strip().lower()
    if topic not in {"orders/paid", "refunds/create"}:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Shopify webhook payload must be an object")

    if topic == "orders/paid":
        order_id = payload.get("id") or payload.get("order_id")
        if order_id is None:
            raise ValueError("Shopify paid order is missing id")
        amount, currency = _order_amount(payload)
        return {
            "event_type": "PURCHASE_APPROVED",
            "external_id": f"orders/paid:{order_id}",
            "amount": float(amount),
            "currency": currency,
            "order_id": str(order_id),
        }

    refund_id = payload.get("id")
    order_id = payload.get("order_id")
    if refund_id is None or order_id is None:
        raise ValueError("Shopify refund is missing refund id or order_id")
    amount, currency = _refund_amount(payload)
    return {
        "event_type": "PURCHASE_REFUNDED",
        "external_id": f"refunds/create:{refund_id}",
        "amount": float(amount),
        "currency": currency,
        "order_id": str(order_id),
        "refund_id": str(refund_id),
    }


def sanitize_shopify_payload(
    topic: str,
    payload: dict[str, Any],
    event: dict[str, Any],
    webhook_id: str | None = None,
) -> dict[str, Any]:
    """Persist only order/refund identifiers and financial metadata, never buyer PII."""
    safe: dict[str, Any] = {
        "topic": str(topic or "").strip().lower(),
        "order_id": event.get("order_id"),
        "amount": event.get("amount"),
        "currency": event.get("currency"),
    }
    if event.get("refund_id") is not None:
        safe["refund_id"] = event["refund_id"]
    if payload.get("created_at"):
        safe["created_at"] = payload["created_at"]
    if payload.get("processed_at"):
        safe["processed_at"] = payload["processed_at"]
    if webhook_id:
        safe["webhook_id"] = str(webhook_id)[:120]
    return safe
