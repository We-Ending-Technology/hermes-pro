from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..db.supabase import SupabaseError
from .commerce_store import CommerceStore
from .controls import ControlService
from .persistence import PersistentStore


class ServiceSearchRequest(BaseModel):
    query: str = Field(default="ai automation", min_length=2, max_length=120)
    limit: int = Field(default=12, ge=1, le=50)


class ChannelPublishRequest(BaseModel):
    channel: str
    product_id: str
    dry_run: bool = True


def build_commerce_router(store: PersistentStore, commerce: CommerceStore, controls: ControlService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/commerce", tags=["commerce"])

    @router.get("/health")
    async def health() -> dict[str, Any]:
        settings = get_settings()
        supabase = False
        try:
            supabase = await store.db.health()
        except Exception:
            pass
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "api": True,
            "ai_configured": settings.ai_configured,
            "ai_provider": settings.effective_ai_provider,
            "supabase": supabase,
            "queue": "redis" if getattr(store, "queue_uses_redis", False) else "persistent-supabase",
            "controls": controls.get_status(),
        }

    @router.get("/logs")
    async def logs(limit: int = 50) -> list[dict[str, Any]]:
        try:
            return await commerce.list_events()[:limit]
        except TypeError:
            events = await commerce.list_events()
            return events[:limit]
        except SupabaseError as exc:
            raise HTTPException(status_code=503, detail="Eventos indisponíveis") from exc

    @router.get("/channels")
    async def channels() -> list[dict[str, Any]]:
        settings = get_settings()
        hotmart_ready = bool(settings.hotmart_client_id and settings.hotmart_client_secret)
        return [
            {"id": "hermes_catalog", "name": "Hermes Catalog", "type": "internal", "enabled": True,
             "capabilities": ["create_product", "upload_file", "set_price", "publish", "get_status"],
             "requires_external_account": False},
            {"id": "hotmart", "name": "Hotmart", "type": "marketplace", "enabled": hotmart_ready,
             "capabilities": ["get_product", "get_sales", "get_orders", "receive_webhook", "read_catalog"],
             "requires_external_account": True,
             "publication_note": "Somente capacidades documentadas/configuradas são expostas; não há criação fictícia de produto."},
            {"id": "manual_export", "name": "Pacote para publicação", "type": "export", "enabled": True,
             "capabilities": ["prepare_product_package", "upload_file"], "requires_external_account": False},
        ]

    @router.post("/services/search")
    async def service_search(request: ServiceSearchRequest) -> dict[str, Any]:
        query = request.query.strip()
        results: list[dict[str, Any]] = []
        # Public discovery only. Hermes does not auto-apply, bypass accounts, or submit applications.
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            try:
                remotive = await client.get("https://remotive.com/api/remote-jobs", params={"search": query})
                if remotive.is_success:
                    for item in remotive.json().get("jobs", [])[: request.limit]:
                        results.append({
                            "source": "remotive",
                            "external_id": str(item.get("id")),
                            "title": item.get("title"),
                            "company": item.get("company_name"),
                            "description": item.get("description", "")[:1200],
                            "url": item.get("url"),
                            "location": item.get("candidate_required_location"),
                            "job_type": item.get("job_type"),
                            "published_at": item.get("publication_date"),
                            "kind": "service_opportunity",
                        })
            except Exception:
                pass
            try:
                arbeit = await client.get("https://www.arbeitnow.com/api/job-board-api", params={"search": query})
                if arbeit.is_success:
                    for item in arbeit.json().get("data", [])[: request.limit]:
                        results.append({
                            "source": "arbeitnow",
                            "external_id": str(item.get("slug") or item.get("id")),
                            "title": item.get("title"),
                            "company": item.get("company_name"),
                            "description": item.get("description", "")[:1200],
                            "url": item.get("url"),
                            "location": item.get("location"),
                            "job_type": item.get("job_types"),
                            "published_at": item.get("created_at"),
                            "kind": "service_opportunity",
                        })
        for item in results:
            try:
                payload = dict(item)
                payload["source_url"] = item.get("url")
                await commerce.create_opportunity(payload, f"service:{item['source']}:{item['external_id']}")
            except Exception:
                pass
        return {"query": query, "count": len(results), "opportunities": results[: request.limit],
                "policy": "discovery_only", "next_action": "evaluate_fit_and_prepare_draft"}

    @router.post("/channels/publish")
    async def publish(request: ChannelPublishRequest) -> dict[str, Any]:
        if not controls.is_allowed("publish").allowed:
            raise HTTPException(status_code=423, detail="Publicação bloqueada pelos controles do Hermes")
        if request.channel not in {"hermes_catalog", "manual_export", "hotmart"}:
            raise HTTPException(status_code=404, detail="Canal desconhecido")
        try:
            product = await store.get_product(request.product_id)
        except SupabaseError as exc:
            raise HTTPException(status_code=503, detail="Persistência indisponível") from exc
        if not product:
            raise HTTPException(status_code=404, detail="product not found")
        if request.dry_run:
            return {"accepted": True, "dry_run": True, "channel": request.channel, "product_id": request.product_id,
                    "message": "Plano de publicação validado; nenhuma publicação externa foi executada."}
        if request.channel == "hotmart":
            return {"accepted": False, "channel": "hotmart", "product_id": request.product_id,
                    "message": "A integração atual não declara criação/publicação de produto via API; ação externa necessária."}
        return {"accepted": True, "channel": request.channel, "product_id": request.product_id,
                "message": "Publicação interna/pacote preparada."}

    return router
