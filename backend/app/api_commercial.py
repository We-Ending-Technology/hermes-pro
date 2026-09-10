from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .services.hotmart import HotmartClient, HotmartError
from .services.integrations import integration_status
from .services.persistence import PersistentStore
from .services.telegram import TelegramNotifier

router = APIRouter()
settings = get_settings()
db = SupabaseREST(settings)
store = PersistentStore(db)
hotmart = HotmartClient(settings)
telegram = TelegramNotifier(settings)


@router.get("/ready")
async def ready() -> dict[str, Any]:
    """Readiness/configuration diagnostics without exposing secret values."""
    configured = {x["name"].lower(): x for x in integration_status()}
    checks: list[dict[str, Any]] = []
    env_fallbacks = {
        "gemini": "GEMINI_API_KEY",
        "supabase": "SUPABASE_URL",
        "redis": "REDIS_URL",
        "hotmart": "HOTMART_CLIENT_ID",
        "telegram": "TELEGRAM_BOT_TOKEN",
    }
    for name, env_name in env_fallbacks.items():
        item = configured.get(name)
        is_ready = bool(item and item.get("status") in {"connected", "ok"})
        if item is None:
            is_ready = bool(os.getenv(env_name))
        checks.append({
            "name": name.capitalize(),
            "status": "ready" if is_ready else "not_configured",
            "configured": is_ready,
            "message": item.get("message", f"{env_name} configurado") if item else f"{env_name} configurado",
        })
    return {"status": "ready" if all(x["configured"] for x in checks) else "degraded", "service": "hermes-pro-api", "checks": checks}


@router.get("/api/v1/hotmart/products")
async def hotmart_products() -> dict[str, Any]:
    try:
        return {"items": await hotmart.list_products()}
    except HotmartError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/v1/hotmart/products/{ucode}/offers")
async def hotmart_offers(ucode: str) -> dict[str, Any]:
    try:
        return {"items": await hotmart.list_offers(ucode)}
    except HotmartError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/api/v1/webhooks/hotmart")
async def hotmart_webhook(request: Request, x_hotmart_hottok: str | None = Header(default=None)) -> dict[str, Any]:
    expected = settings.hotmart_webhook_token
    if expected and x_hotmart_hottok != expected:
        raise HTTPException(status_code=401, detail="invalid Hotmart webhook token")
    payload = await request.json()
    event_type = str(payload.get("event") or payload.get("event_type") or "UNKNOWN")
    event_id = payload.get("id")
    data = payload.get("data") or {}
    purchase = data.get("purchase") or {}
    price = purchase.get("price") or data.get("price") or {}
    amount = price.get("value") if isinstance(price, dict) else None
    currency = price.get("currency_code") if isinstance(price, dict) else None
    try:
        await store.append_event("hotmart", event_type, payload, external_id=str(event_id) if event_id else None, amount=float(amount) if amount is not None else None, currency=currency)
    except SupabaseError as exc:
        if "duplicate" not in str(exc).lower() and "unique" not in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    await telegram.send(f"Hermes Pro / Hotmart\nEvento: {event_type}\nValor: {amount} {currency or ''}".strip())
    return {"ok": True, "event": event_type}
