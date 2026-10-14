from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .services.hotmart import HotmartClient, HotmartError
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
    """Report configuration separately from a real read-only dependency probe."""
    statuses = {x["name"].lower(): x for x in integration_service.status()}
    checks: list[dict[str, Any]] = []
    supabase_key_vars = {
        "SUPABASE_SERVICE_ROLE_KEY": bool(settings.supabase_service_role_key),
        "SUPABASE_SERVICE_KEY": bool(settings.supabase_service_key),
        "SUPABASE_SECRET_KEY": bool(settings.supabase_secret_key),
    }
    non_privileged_key_vars = {
        "SUPABASE_KEY": bool(settings.supabase_key),
        "SUPABASE_ANON_KEY": bool(settings.supabase_anon_key),
        "SUPABASE_PUBLISHABLE_KEY": bool(settings.supabase_publishable_key),
    }
    accepted_key = bool(db.secret_key)
    key_kind = "sb_secret" if (db.secret_key or "").startswith("sb_secret_") else "service_role_jwt" if db.secret_key else "missing_or_not_privileged"
    if not accepted_key:
        if any(supabase_key_vars.values()):
            key_message = "Uma variável de chave do servidor existe, mas seu valor não foi reconhecido como service_role JWT ou sb_secret_*. Confira se não é uma chave anon/publishable."
        elif any(non_privileged_key_vars.values()):
            key_message = "Foram detectadas apenas variáveis genéricas/anon/publishable. Elas não autorizam gravações do worker; configure SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_SECRET_KEY com a chave privilegiada do projeto."
        else:
            key_message = "Nenhuma chave privilegiada foi encontrada nos nomes aceitos. Configure SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_SECRET_KEY com a chave de servidor do projeto."
    else:
        key_message = "Chave privilegiada reconhecida; testando leitura real no Supabase."
    for name in ("Gemini", "Supabase", "Redis", "Hotmart", "Telegram"):
        item = statuses[name.lower()]
        configured = item["status"] not in {"not_configured", "error", "offline"}
        status = "configured" if configured else "not_configured"
        message = item["message"]
        if name == "Supabase":
            message = key_message
            if configured:
                connected = await db.health()
                status = "connected" if connected else "error"
                message = "Leitura de teste em hermes_products funcionou." if connected else "Chave reconhecida, mas a leitura de teste no Supabase falhou. Verifique URL, permissões e chave de servidor."
        checks.append({
            "name": name,
            "status": status,
            "configured": configured,
            "connected": status == "connected" if name == "Supabase" else None,
            "message": message,
        })
    required_ok = all(x["configured"] for x in checks if x["name"] in {"Gemini", "Supabase"})
    supabase_connected = next((x.get("connected") for x in checks if x["name"] == "Supabase"), False)
    status = "ready" if required_ok and supabase_connected else "degraded"
    return {
        "status": status,
        "service": "hermes-pro-api",
        "checks": checks,
        "credential_diagnostics": {
            "supabase_url_present": bool(settings.supabase_url),
            "server_key_variables_present": supabase_key_vars,
            "non_privileged_key_variables_present": non_privileged_key_vars,
            "accepted_server_key": accepted_key,
            "accepted_server_key_type": key_kind,
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
    except SupabaseError as exc:
        if "duplicate" not in str(exc).lower() and "unique" not in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    await telegram.send(f"Hermes Pro / Hotmart\nEvento: {event_type}\nValor: {amount} {currency or ''}".strip())
    return {"ok": True, "event": event_type}
