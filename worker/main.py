from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.document_assets import build_cover, build_docx, build_pdf, normalize_content
from backend.app.services.persistence import PersistentStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes.worker")
MAX_ATTEMPTS = 3


async def process_product(job_id: str, store: PersistentStore, queue: JobQueue) -> None:
    job = await store.get_job(job_id)
    if not job or job["job_type"] != "product_generation" or job["status"] == "completed":
        return
    attempts = int(job["attempts"]) + 1
    if attempts > MAX_ATTEMPTS:
        await store.update_job(job_id, "failed", attempts=int(job["attempts"]), error_message="maximum attempts reached")
        return
    payload = job.get("payload") or {}
    product_id, topic = payload.get("product_id"), payload.get("topic")
    if not product_id or not topic:
        await store.update_job(job_id, "failed", attempts=attempts, error_message="invalid product_generation payload")
        return
    try:
        await store.update_job(job_id, "running", attempts=attempts, error_message=None)
        settings = get_settings()
        if not settings.ai_configured:
            raise RuntimeError("AI Gateway indisponível: GEMINI_API_KEY/GOOGLE_API_KEY não está configurada")
        gateway = build_ai_gateway(settings)
        await store.update_product(product_id, status="generating", current_stage="topic")
        strategist = await gateway.complete(
            f"Create a concise product strategy for the digital ebook topic: {topic}. Return valid JSON with keys: positioning, audience, title, subtitle, outline (array of chapter titles).",
            system="You are the Hermes Pro strategist. Return only valid JSON. Do not claim market data you do not have.",
        )
        strategy_data = json.loads(strategist.content)
        await store.update_product(product_id, current_stage="writer")
        writer = await gateway.complete(
            f"Using this strategy, write the ebook for topic '{topic}'. Strategy: {strategist.content}\nReturn valid JSON with keys: introduction, chapters (array of objects with title and content), conclusion.",
            system="You are the Hermes Pro writer. Return only valid JSON. Produce original, useful educational content and do not fabricate citations.",
        )
        content = normalize_content(writer.content)
        await store.update_product(product_id, current_stage="reviewer")
        reviewer = await gateway.complete(
            f"Review this proposed ebook for topic '{topic}'. Identify factual, structural and readability problems and provide a quality score from 0-100. Return valid JSON with keys: score, findings (array), approved (boolean).\nSTRATEGY: {strategist.content}\nEBOOK: {writer.content}",
            system="You are the Hermes Pro reviewer. Return only valid JSON. Be conservative: approval requires score >= 80.",
        )
        review_data = json.loads(reviewer.content)
        score = int(review_data.get("score", 0))
        approved = bool(review_data.get("approved")) and score >= 80
        title = str(strategy_data.get("title") or topic)
        subtitle = str(strategy_data.get("subtitle") or "")
        metadata = {
            "strategy": strategy_data,
            "content": content,
            "review": review_data,
            "quality_score": score,
            "ai_provider": strategist.provider,
            "ai_model": strategist.model,
            "content_versions": [{"id": "initial", "created_at": datetime.now(timezone.utc).isoformat(), "note": "Geração inicial", "content": content}],
            "offer": {"title": title, "subtitle": subtitle, "description": f"Ebook sobre {topic}.", "price": 19.90, "currency": "BRL"},
            "subtitle": subtitle,
            "description": f"Ebook sobre {topic}.",
            "suggested_price": 19.90,
            "short_description": f"Ebook prático sobre {topic}.",
        }
        await store.update_product(product_id, current_stage="validation", title=title, metadata=metadata)
        if not approved:
            await store.update_product(product_id, status="review_required", current_stage="reviewer", metadata=metadata)
            await store.update_job(job_id, "completed", attempts=attempts)
            return
        await store.update_product(product_id, current_stage="document")
        db = store.db
        docx = build_docx(title, content)
        pdf = build_pdf(title, content)
        cover = build_cover(title, subtitle)
        stamp = uuid4().hex
        docx_path, pdf_path, cover_path = f"{product_id}/{stamp}.docx", f"{product_id}/{stamp}.pdf", f"{product_id}/{stamp}.png"
        await db.upload_storage("ebooks", docx_path, docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        await db.upload_storage("exports", pdf_path, pdf, "application/pdf")
        await db.upload_storage("covers", cover_path, cover, "image/png")
        assets = {
            "docx": {"path": docx_path, "url": await db.create_signed_url("ebooks", docx_path)},
            "pdf": {"path": pdf_path, "url": await db.create_signed_url("exports", pdf_path)},
            "cover": {"path": cover_path, "url": await db.create_signed_url("covers", cover_path)},
        }
        metadata["assets"] = assets
        metadata["document_url"] = assets["docx"]["url"]
        metadata["pdf_url"] = assets["pdf"]["url"]
        metadata["cover_url"] = assets["cover"]["url"]
        metadata["cover_versions"] = [{"id": "initial", "path": cover_path, "url": assets["cover"]["url"], "prompt": "capa editorial premium", "active": True}]
        metadata["active_cover"] = metadata["cover_versions"][0]
        await store.update_product(product_id, status="ready_to_sell", current_stage="publication", metadata=metadata)
        await store.update_job(job_id, "completed", attempts=attempts)
    except Exception as exc:
        message = str(exc)[:1000]
        if attempts < MAX_ATTEMPTS:
            await store.update_job(job_id, "retrying", attempts=attempts, error_message=message)
            await queue.enqueue(job_id)
        else:
            await store.update_job(job_id, "failed", attempts=attempts, error_message=message)
            await store.update_product(product_id, status="failed")
        logger.exception("product_generation failed job=%s", job_id)


async def recover_pending(store: PersistentStore, queue: JobQueue) -> None:
    for job in await store.list_jobs():
        if job["job_type"] == "product_generation" and job["status"] in {"pending", "retrying"}:
            await queue.enqueue(str(job["id"]))


async def run() -> None:
    settings = get_settings()
    store = PersistentStore(SupabaseREST(settings))
    queue = JobQueue(settings.redis_url, store.db)
    logger.info("Hermes Pro worker started; queue=%s", "redis" if queue.uses_redis else "supabase")
    try:
        await recover_pending(store, queue)
        while True:
            job_id = await queue.dequeue(timeout=10)
            if job_id:
                await process_product(job_id, store, queue)
            else:
                await recover_pending(store, queue)
    finally:
        await queue.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Hermes Pro worker stopped")
