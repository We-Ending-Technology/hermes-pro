from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db.supabase import SupabaseError, SupabaseREST
from .document_assets import build_cover, build_docx, build_pdf, normalize_content
from .persistence import PersistentStore


class StudioSaveRequest(BaseModel):
    content: dict[str, Any]
    note: str = Field(default="Edição manual", max_length=500)


class CoverRequest(BaseModel):
    prompt: str = Field(default="capa editorial premium", max_length=1000)
    subtitle: str = Field(default="", max_length=240)


def build_studio_router(store: PersistentStore, db: SupabaseREST) -> APIRouter:
    router = APIRouter(prefix="/api/v1/studio", tags=["studio"])

    @router.get("/{product_id}")
    async def get_studio(product_id: str) -> dict[str, Any]:
        try:
            product = await store.get_product(product_id)
        except SupabaseError as exc:
            raise HTTPException(status_code=503, detail="Persistência Supabase indisponível.") from exc
        if not product:
            raise HTTPException(status_code=404, detail="product not found")
        metadata = dict(product.get("metadata") or {})
        versions = metadata.get("content_versions") or []
        content = metadata.get("content") or {"introduction": "", "chapters": [], "conclusion": ""}
        return {"product_id": product_id, "title": product.get("title"), "content": normalize_content(content), "versions": versions, "assets": metadata.get("assets") or {}, "offer": metadata.get("offer") or {}}

    @router.put("/{product_id}")
    async def save_studio(product_id: str, request: StudioSaveRequest) -> dict[str, Any]:
        try:
            product = await store.get_product(product_id)
            if not product:
                raise HTTPException(status_code=404, detail="product not found")
            metadata = dict(product.get("metadata") or {})
            versions = list(metadata.get("content_versions") or [])
            version = {"id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat(), "note": request.note, "content": normalize_content(request.content)}
            versions.append(version)
            metadata["content_versions"] = versions
            metadata["content"] = version["content"]
            metadata.pop("assets", None)
            updated = await store.update_product(product_id, metadata=metadata, status="editing", current_stage="document")
        except SupabaseError as exc:
            raise HTTPException(status_code=503, detail="Falha ao salvar a versão do ebook.") from exc
        return {"product_id": product_id, "version": version, "product": updated}

    @router.post("/{product_id}/regenerate")
    async def regenerate_assets(product_id: str) -> dict[str, Any]:
        try:
            product = await store.get_product(product_id)
            if not product:
                raise HTTPException(status_code=404, detail="product not found")
            metadata = dict(product.get("metadata") or {})
            content = normalize_content(metadata.get("content") or {})
            title = product.get("title") or product.get("topic") or "Ebook"
            docx = build_docx(title, content)
            pdf = build_pdf(title, content)
            stamp = uuid4().hex
            docx_path = f"{product_id}/{stamp}.docx"
            pdf_path = f"{product_id}/{stamp}.pdf"
            await db.upload_storage("ebooks", docx_path, docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            await db.upload_storage("exports", pdf_path, pdf, "application/pdf")
            docx_url = await db.create_signed_url("ebooks", docx_path)
            pdf_url = await db.create_signed_url("exports", pdf_path)
            assets = dict(metadata.get("assets") or {})
            assets.update({"docx": {"path": docx_path, "url": docx_url}, "pdf": {"path": pdf_path, "url": pdf_url}})
            metadata["assets"] = assets
            metadata["content"] = content
            updated = await store.update_product(product_id, metadata=metadata, status="document_ready", current_stage="document")
        except SupabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"product": updated, "assets": assets}

    @router.post("/{product_id}/cover")
    async def generate_cover(product_id: str, request: CoverRequest) -> dict[str, Any]:
        try:
            product = await store.get_product(product_id)
            if not product:
                raise HTTPException(status_code=404, detail="product not found")
            title = product.get("title") or product.get("topic") or "Ebook"
            metadata = dict(product.get("metadata") or {})
            image = build_cover(title, request.subtitle)
            path = f"{product_id}/{uuid4().hex}.png"
            await db.upload_storage("covers", path, image, "image/png")
            url = await db.create_signed_url("covers", path)
            covers = list(metadata.get("cover_versions") or [])
            cover = {"id": str(uuid4()), "path": path, "url": url, "prompt": request.prompt, "created_at": datetime.now(timezone.utc).isoformat(), "active": True}
            for item in covers:
                item["active"] = False
            covers.append(cover)
            metadata["cover_versions"] = covers
            metadata["active_cover"] = cover
            updated = await store.update_product(product_id, metadata=metadata, current_stage="cover", status="cover_ready")
        except SupabaseError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"product": updated, "cover": cover}

    return router
