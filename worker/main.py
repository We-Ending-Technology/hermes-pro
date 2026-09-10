from __future__ import annotations

import asyncio
import json
import logging

from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.persistence import PersistentStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes.worker")

MAX_ATTEMPTS = 3


async def process_product(job_id: str, store: PersistentStore, queue: JobQueue) -> None:
    job = await store.get_job(job_id)
    if not job or job["job_type"] != "product_generation":
        return
    if job["status"] == "completed":
        return
    if int(job["attempts"]) >= MAX_ATTEMPTS:
        await store.update_job(job_id, "failed", attempts=job["attempts"], error_message="maximum attempts reached")
        return

    attempts = int(job["attempts"]) + 1
    product_id = (job.get("payload") or {}).get("product_id")
    topic = (job.get("payload") or {}).get("topic")
    if not product_id or not topic:
        await store.update_job(job_id, "failed", attempts=attempts, error_message="invalid product_generation payload")
        return

    try:
        await store.update_job(job_id, "running", attempts=attempts, error_message=None)
        gateway = build_ai_gateway(get_settings())
        await store.update_product(product_id, status="generating", current_stage="topic")
        strategist = await gateway.complete(
            f"Create a concise product strategy for the digital ebook topic: {topic}. Return valid JSON with keys: positioning, audience, title, subtitle, outline (array of chapter titles).",
            system="You are the Hermes Pro strategist. Return only valid JSON. Do not claim market data you do not have.",
        )
        await store.update_product(product_id, current_stage="writer")
        writer = await gateway.complete(
            f"Using this strategy, write the ebook for topic '{topic}'. Strategy: {strategist.content}\nReturn valid JSON with keys: introduction, chapters (array of objects with title and content), conclusion.",
            system="You are the Hermes Pro writer. Return only valid JSON. Produce original, useful educational content and do not fabricate citations.",
        )
        await store.update_product(product_id, current_stage="reviewer")
        reviewer = await gateway.complete(
            f"Review this proposed ebook for topic '{topic}'. Identify factual, structural and readability problems and provide a quality score from 0-100. Return valid JSON with keys: score, findings (array), approved (boolean).\nSTRATEGY: {strategist.content}\nEBOOK: {writer.content}",
            system="You are the Hermes Pro reviewer. Return only valid JSON. Be conservative: approval requires score >= 80.",
        )
        await store.update_product(product_id, current_stage="validation")
        try:
            strategy_data = json.loads(strategist.content)
            review_data = json.loads(reviewer.content)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Gemini returned invalid JSON for the product pipeline") from exc

        score = int(review_data.get("score", 0))
        approved = bool(review_data.get("approved")) and score >= 80
        metadata = {
            "strategy": strategy_data,
            "content": writer.content,
            "review": review_data,
            "quality_score": score,
            "ai_provider": strategist.provider,
            "ai_model": strategist.model,
        }
        title = strategy_data.get("title") if isinstance(strategy_data, dict) else None
        if not approved:
            await store.update_product(product_id, status="review_required", current_stage="reviewer", title=title, metadata=metadata)
        else:
            # This job completes the AI content phase only. Document, cover and publication must not be marked complete here.
            await store.update_product(product_id, status="content_ready", current_stage="validation", title=title, metadata=metadata)
        await store.update_job(job_id, "completed", attempts=attempts)
        logger.info("completed product_generation job=%s product=%s approved=%s", job_id, product_id, approved)
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
    queue = JobQueue(settings.redis_url)
    logger.info("Hermes Pro worker started; queue=hermes:jobs:product_generation")
    try:
        await recover_pending(store, queue)
        while True:
            job_id = await queue.dequeue(timeout=10)
            if job_id:
                await process_product(job_id, store, queue)
            else:
                # Recovery path: jobs survive worker/Redis restarts because their source of truth is Supabase.
                await recover_pending(store, queue)
    finally:
        await queue.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Hermes Pro worker stopped")
