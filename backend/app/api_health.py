from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from .services.integrations import integration_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: the API process is alive."""
    return {"status": "ok", "service": "hermes-pro-api"}


def _ready_item(name: str, configured: bool, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "ready" if configured else "not_configured",
        "configured": configured,
        "message": message,
    }


@router.get("/ready")
def ready() -> dict[str, Any]:
    """Readiness/configuration diagnostics without exposing secrets."""
    configured = {x["name"].lower(): x for x in integration_status()}
    items = []
    for name, env_name in (
        ("Gemini", "GEMINI_API_KEY"),
        ("Supabase", "SUPABASE_URL"),
        ("Redis", "REDIS_URL"),
        ("Hotmart", "HOTMART_CLIENT_ID"),
        ("Telegram", "TELEGRAM_BOT_TOKEN"),
    ):
        value = configured.get(name.lower())
        is_configured = bool(value and value.get("status") in {"connected", "ok"})
        if value is None:
            is_configured = bool(os.getenv(env_name))
        items.append(_ready_item(name, is_configured, value.get("message", "") if value else f"{env_name} configurado"))

    all_ready = all(x["configured"] for x in items)
    return {"status": "ready" if all_ready else "degraded", "service": "hermes-pro-api", "checks": items}
