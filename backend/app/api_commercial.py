from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .core.config import get_settings
from .db.postgres import PostgresStore, DatabaseError
from .services.hotmart import HotmartClient, HotmartError
from .services.integrations import integration_service
from .services.persistence import PersistentStore
from .services.telegram import TelegramNotifier

router = APIRouter()
settings = get_settings()
db = PostgresStore(settings)
store = PersistentStore(db)
hotmart = HotmartClient(settings)
telegram = TelegramNotifier(settings)


@router.get("/ready")
async def ready() -> dict[str, Any]:
    """Check real PostgreSQL connectivity separately from optional integrations."""
    statuses = {x["name"].lower(): x for x in integration_service.status()}
    database_configured = bool(settings.database_url and "${{" not in settings.database_url)
    database_connected = await db.health()
    checks: list[dict[str, Any]] = [{
        "name": "PostgreSQL",
        "status": "connected" if database_connected else "error",
        "configured": database_configured,
        "connected": database_connected,
        "message": "Conexão PostgreSQL verificada." if database_connected else (
            "DATABASE_URL ausente ou ainda contém uma referência de template."
            if not database_configured else
            "A conexão PostgreSQL falhou; confira a URL interna e as permissões de rede."
        ),
    }]
    for name in ("Gemini", "Redis", "Hotmart", "Telegram"):
        item = statuses.get(name.lower(), {})
        configured = item.get("status") not in {None, "not_configured", "error", "offline"}
        checks.append({
            "name": name,
            "status": "configured" if configured else "not_configured",
            "configured": configured,
            "connected": None,
            "message": item.get("message", "Estado da integração indisponível."),
        })
    gemini_configured = next((x["configured"] for x in checks if x["name"] == "Gemini"), False)
    status = "ready" if database_connected and gemini_configured else "degraded"
    return {
        "status": status,
        "service": "hermes-pro-api",
        "checks": checks,
        "credential_diagnostics": {
            "database_url_present": bool(settings.database_url),
            "database_url_is_template": "${{" in (settings.database_url or ""),
            "secret_values_exposed": False,
        },
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
    # Fail closed: never accept unsigned webhook events when the secret is missing.
    if not expected:
        raise HTTPException(status_code=503, detail="Hotmart webhook authentication is not configured")
    if not x_hotmart_hottok or x_hotmart_hottok != expected:
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
    except DatabaseError as exc:
        if "duplicate" not in str(exc).lower() and "unique" not in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    await telegram.send(f"Hermes Pro / Hotmart\nEvento: {event_type}\nValor: {amount} {currency or ''}".strip())
    return {"ok": True, "event": event_type}
