from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .services.hotmart import HotmartClient, HotmartError
from .services.integrations import integration_service
from .queue import JobQueue
from .services.artifacts import build_artifacts
from .services.storage import SupabaseStorage
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
    statuses = {x["name"].lower(): x for x in integration_service.status()}
    checks: list[dict[str, Any]] = []
    for name in ("Gemini", "Supabase", "Redis", "Hotmart", "Telegram"):
        item = statuses[name.lower()]
        is_ready = item["status"] not in {"not_configured", "error", "offline"}
        checks.append({
            "name": name,
            "status": "ready" if is_ready else "not_configured",
            "configured": is_ready,
            "message": item["message"],
        })
    return {"status": "ready" if all(x["configured"] for x in checks) else "degraded", "service": "hermes-pro-api", "checks": checks}


@router.get("/api/v1/operations")
async def operations() -> dict[str, Any]:
    return {
        "kill_switch": settings.hermes_kill_switch,
        "automation": "blocked" if settings.hermes_kill_switch else "armed",
        "worker": "enabled" if settings.redis_url else "not_configured",
        "scheduler": {"enabled": not settings.hermes_kill_switch, "type": "render_cron", "schedule": "*/15 * * * *", "task": "maintenance/recovery"},
        "queue": {"name": "hermes:jobs:product_generation", "backend": "redis", "configured": bool(settings.redis_url)},
        "integrations": integration_service.status(),
    }


@router.post("/api/v1/jobs/{job_id}/retry")
async def retry_job(job_id: str) -> dict[str, Any]:
    job = await store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if settings.hermes_kill_switch:
        raise HTTPException(status_code=423, detail="automation blocked by kill switch")
    if job["status"] in {"pending", "running", "retrying"}:
        return job
    if job["status"] == "completed":
        raise HTTPException(status_code=409, detail="completed job cannot be retried")
    attempts = int(job.get("attempts") or 0)
    if attempts >= int(job.get("max_attempts") or 3):
        raise HTTPException(status_code=409, detail="maximum attempts reached; create a new job")
    updated = await store.update_job(job_id, "pending", error_message=None)
    queue = JobQueue(settings.redis_url)
    try:
        await queue.enqueue(job_id)
    finally:
        await queue.close()
    return updated


@router.post("/api/v1/products/{product_id}/ebook/regenerate")
async def regenerate_ebook_artifacts(product_id: str) -> dict[str, Any]:
    row = await store.get_product(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="product not found")
    metadata = dict(row.get("metadata") or {})
    content_data = metadata.get("content_data") or {}
    content = metadata.get("content") or ""
    strategy = dict(metadata.get("strategy") or {})
    title = str(row.get("title") or strategy.get("title") or row.get("topic") or "Ebook").strip()
    subtitle = str(strategy.get("subtitle") or "")
    if not content_data and not content:
        raise HTTPException(status_code=409, detail="ebook has no persisted content to regenerate")
    if not content:
        import json
        content = json.dumps(content_data, ensure_ascii=False)
    try:
        metadata["artifact_status"] = "generating"
        await store.update_product(product_id, status="generating_artifacts", current_stage="studio", metadata=metadata)
        artifacts = build_artifacts(title, subtitle, content)
        storage = SupabaseStorage(settings)
        urls: dict[str, str] = {}
        for kind, (artifact_path, blob, content_type) in artifacts.items():
            urls[kind] = await storage.upload(f"{product_id}/{artifact_path}", blob, content_type)
        metadata["artifacts"] = urls
        metadata["artifact_status"] = "ready"
        metadata.pop("artifact_error", None)
        updated = await store.update_product(product_id, status="ready_to_publish", current_stage="studio", metadata=metadata)
        return {"id": product_id, "title": title, "subtitle": subtitle, "artifacts": urls, "artifact_status": "ready", "status": updated.get("status")}
    except Exception as exc:
        metadata["artifact_status"] = "error"
        metadata["artifact_error"] = str(exc)[:1000]
        await store.update_product(product_id, status="artifact_error", current_stage="studio", metadata=metadata)
        raise HTTPException(status_code=503, detail=f"artifact regeneration failed: {exc}") from exc


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
