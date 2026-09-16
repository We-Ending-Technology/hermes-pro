from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..core.config import get_settings
from ..services.persistence import PersistentStore
from .hotmart import HotmartAdapter, HotmartError


def build_hotmart_router(store: PersistentStore) -> APIRouter:
    router = APIRouter(prefix="/api/v1/hotmart", tags=["hotmart"])
    adapter = HotmartAdapter(get_settings())

    @router.get("/capabilities")
    async def capabilities() -> dict:
        return adapter.publication_capabilities()

    @router.get("/products")
    async def products() -> dict:
        try:
            return await adapter.list_products()
        except HotmartError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.get("/sales")
    async def sales() -> dict:
        try:
            return await adapter.sales_history()
        except HotmartError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.post("/webhook")
    async def webhook(request: Request) -> dict[str, object]:
        payload = await request.json()
        token = request.headers.get("x-hotmart-hottok") or request.headers.get("hottok")
        expected = get_settings().hotmart_webhook_token
        if expected and token != expected:
            raise HTTPException(status_code=401, detail="invalid Hotmart webhook token")
        external_id = str(payload.get("data", {}).get("purchase", {}).get("transaction") or payload.get("id") or "")
        if not external_id:
            raise HTTPException(status_code=400, detail="webhook transaction id is required")
        try:
            await store.append_event("hotmart", str(payload.get("event") or "unknown"), payload, external_id=external_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="failed to persist Hotmart webhook") from exc
        return {"accepted": True, "external_id": external_id}

    return router
