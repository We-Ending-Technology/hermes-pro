from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from redis.asyncio import Redis

from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .services.hotmart import HotmartClient, HotmartError
from .services.kiwify import normalize_kiwify_event, sanitize_kiwify_payload, verify_kiwify_signature
from .services.integrations import integration_service
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
    """Check live dependencies; never expose secret values."""
    supabase_ok = await db.health()
    redis_ok = False
    if settings.redis_url:
        client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        try:
            redis_ok = bool(await client.ping())
        except Exception:
            redis_ok = False
        finally:
            await client.aclose()

    provider = settings.ai_provider.strip().lower()
    if provider == "gemini":
        primary_ai_ok = bool(settings.gemini_api_key or settings.ai_api_key)
    elif provider == "openai":
        primary_ai_ok = bool(settings.openai_api_key)
    else:
        primary_ai_ok = False
    fallback_provider = (settings.ai_fallback_provider or "").strip().lower()
    fallback_ai_ok = (
        fallback_provider == "openai" and bool(settings.openai_api_key)
    ) or (
        fallback_provider == "gemini" and bool(settings.gemini_api_key or settings.ai_api_key)
    )
    ai_ok = primary_ai_ok or fallback_ai_ok
    ai_message = "Primary configured: " + str(primary_ai_ok) + "; fallback " + fallback_provider + " configured: " + str(fallback_ai_ok)

    configured = {x["name"].lower(): x for x in integration_service.status()}
    checks: list[dict[str, Any]] = [
        {
            "name": "Supabase",
            "status": "ready" if supabase_ok else "error",
            "configured": supabase_ok,
            "message": "Conexão REST validada" if supabase_ok else "Banco inacessível ou credencial de servidor inválida.",
            "required": True,
        },
        {
            "name": "Redis",
            "status": "ready" if redis_ok else "error",
            "configured": redis_ok,
            "message": "PING confirmado" if redis_ok else "Fila indisponível; verifique REDIS_URL e o serviço Key Value.",
            "required": True,
        },
        {
            "name": "AI",
            "status": "ready" if ai_ok else "error",
            "configured": ai_ok,
            "message": ai_message if ai_ok else "Nenhum provedor de IA real está configurado.",
            "required": True,
        },
    ]

    for name in ("Hotmart", "Kiwify", "Telegram"):
        item = configured[name.lower()]
        checks.append({
            "name": name,
            "status": "ready" if item["status"] == "connected" else "optional_missing",
            "configured": item["status"] == "connected",
            "message": item["message"],
            "required": False,
        })

    critical_ready = all(item["configured"] for item in checks if item["required"])
    return {
        "status": "ready" if critical_ready else "degraded",
        "service": "hermes-pro-api",
        "checks": checks,
    }


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
    if not expected:
        raise HTTPException(status_code=503, detail="Hotmart webhook token is not configured")
    if not hmac.compare_digest(x_hotmart_hottok or "", expected):
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



@router.post("/api/v1/webhooks/kiwify")
async def kiwify_webhook(request: Request) -> dict[str, Any]:
    """Receive Kiwify JSON events signed with HMAC-SHA1 over the raw body."""
    secret = settings.kiwify_webhook_token or ""
    if not secret:
        raise HTTPException(status_code=503, detail="Kiwify webhook signing token is not configured")

    raw_body = await request.body()
    signature = request.query_params.get("signature", "")
    if not verify_kiwify_signature(raw_body, secret, signature):
        raise HTTPException(status_code=401, detail="invalid Kiwify webhook signature")

    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="webhook payload must be a JSON object")

    try:
        event = normalize_kiwify_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        await store.append_event(
            "kiwify",
            event["event_type"],
            sanitize_kiwify_payload(payload),
            external_id=event["external_id"],
            amount=event["amount"],
            currency=event["currency"],
        )
    except SupabaseError as exc:
        message = str(exc).lower()
        if "duplicate" in message or "unique" in message or "23505" in message:
            return {"ok": True, "duplicate": True, "event": event["event_type"]}
        raise HTTPException(status_code=503, detail="could not persist Kiwify event; webhook may be retried") from exc

    return {"ok": True, "duplicate": False, "event": event["event_type"]}
