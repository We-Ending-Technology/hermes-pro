from __future__ import annotations

import io
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from PIL import Image

from .core.config import get_settings
from .db.supabase import SupabaseREST
from .services.ai_images import AIImageError, generate_cover_artwork
from .services.artifacts import build_cover
from .services.persistence import PersistentStore
from .services.storage import StorageError, SupabaseStorage

router = APIRouter(prefix="/api/v1/products", tags=["ebook-covers"])
settings = get_settings()
store = PersistentStore(SupabaseREST(settings))


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")[:80] or "ebook"


def _validate_cover(data: bytes) -> tuple[int, int]:
    if not data or not data.startswith(bytes.fromhex("89504e470d0a1a0a")):
        raise ValueError("A capa gerada não é um PNG válido.")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
    if width < 1200 or height < 1800:
        raise ValueError(f"Resolução da capa abaixo do padrão: {width}x{height}.")
    if height <= width:
        raise ValueError("A capa precisa estar em orientação vertical.")
    return width, height


@router.post("/{product_id}/cover")
async def generate_product_cover(product_id: str, force: bool = False):
    """Dedicated free-only cover agent: generate, compose, validate and persist a product cover."""
    product = await store.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    metadata = dict(product.get("metadata") or {})
    content_data = metadata.get("content_data")
    if not isinstance(content_data, dict):
        raise HTTPException(status_code=409, detail="O ebook ainda não possui conteúdo estruturado para orientar a capa.")

    provider = str(settings.ai_image_provider or "ovhcloud").strip().lower()
    if provider not in {"ovhcloud", "aihorde"}:
        raise HTTPException(
            status_code=409,
            detail="Agente de Capas bloqueado: somente provedores de imagem gratuitos (OVHcloud ou AI Horde) são permitidos.",
        )

    title = str(product.get("title") or content_data.get("title") or product.get("topic") or "Ebook Hermes").strip()
    subtitle = str(content_data.get("subtitle") or metadata.get("subtitle") or "Guia prático ilustrado").strip()
    artifact_paths = dict(metadata.get("artifact_paths") or {})
    existing_cover = artifact_paths.get("cover") if isinstance(artifact_paths.get("cover"), dict) else None
    storage = SupabaseStorage(settings, bucket="covers")

    if existing_cover and existing_cover.get("path") and not force:
        try:
            url = await storage.create_signed_url(str(existing_cover["path"]), expires_in=604800)
            artifacts = dict(metadata.get("artifacts") or {})
            artifacts["cover"] = url
            metadata["artifacts"] = artifacts
            metadata["artifact_urls_expires_at"] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
            await store.update_product(product_id, metadata=metadata)
            return {
                "status": "already_exists",
                "product_id": product_id,
                "cover_url": url,
                "artifact_path": existing_cover["path"],
                "provider": (metadata.get("cover_art") or {}).get("provider", "existing"),
                "validated": True,
            }
        except StorageError:
            pass

    try:
        artwork = await generate_cover_artwork(title, subtitle, content_data, settings)
        cover_png = await __import__("asyncio").to_thread(build_cover, title, subtitle, artwork)
        width, height = await __import__("asyncio").to_thread(_validate_cover, cover_png)
        object_path = f"{product_id}/{_slug(title)}/cover.png"
        cover_url = await storage.upload(object_path, cover_png, "image/png")

        artifacts = dict(metadata.get("artifacts") or {})
        artifacts["cover"] = cover_url
        artifact_paths["cover"] = {"bucket": "covers", "path": object_path}
        metadata["artifacts"] = artifacts
        metadata["artifact_paths"] = artifact_paths
        metadata["artifact_urls_expires_at"] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        metadata["cover_art"] = {
            "provider": provider,
            "model": settings.ovhcloud_image_model if provider == "ovhcloud" else settings.ai_horde_model,
            "generated": True,
            "license_basis": "Free image endpoint; verify the underlying model license before commercial distribution.",
        }
        metadata["cover_agent"] = {
            "status": "completed",
            "provider": provider,
            "validated": True,
            "width": width,
            "height": height,
            "storage_bucket": "covers",
            "storage_path": object_path,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        await store.update_product(product_id, metadata=metadata)
        return {
            "status": "completed",
            "product_id": product_id,
            "cover_url": cover_url,
            "artifact_path": object_path,
            "provider": provider,
            "dimensions": {"width": width, "height": height},
            "validated": True,
        }
    except (AIImageError, StorageError, ValueError) as exc:
        metadata["cover_agent"] = {
            "status": "failed",
            "provider": provider,
            "validated": False,
            "error": str(exc)[:500],
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await store.update_product(product_id, metadata=metadata)
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=f"Agente de Capas não concluiu: {str(exc)[:300]}") from exc
