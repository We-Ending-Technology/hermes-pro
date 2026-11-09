from __future__ import annotations

import asyncio
import json
import logging

from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.artifacts import build_artifacts
from backend.app.services.persistence import PersistentStore
from backend.app.services.storage import SupabaseStorage
from worker.agent_jobs import process_agent
from worker.autonomy_scheduler import autonomy_tick
from worker.json_utils import build_review_excerpt, parse_json_object

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes.worker")
MAX_ATTEMPTS = 3
RECOVERY_INTERVAL_SECONDS = 300
ARTIFACT_BUCKETS = {"cover": "covers", "docx": "exports", "pdf": "ebooks"}


async def complete_json_response(
    gateway: Any,
    prompt: str,
    system: str,
    *,
    label: str,
    fallback: dict | None = None,
):
    """Request structured JSON, repair one malformed response, and fail closed when needed."""
    result = await gateway.complete(prompt, system=system)
    try:
        return result, parse_json_object(result.content)
    except ValueError as exc:
        logger.warning("%s returned invalid JSON (%s); requesting one repair", label, str(exc)[:180])

    repair_prompt = (
        "Your previous answer was empty or invalid. Return exactly one valid JSON object, "
        "with no Markdown fences, no preamble, and no text outside the JSON object.\n"
        f"Original task:\n{prompt[:12000]}\n"
        f"Previous response:\n{(result.content or '')[:3000]}"
    )
    repaired = await gateway.complete(repair_prompt, system=system)
    try:
        return repaired, parse_json_object(repaired.content)
    except ValueError as exc:
        if fallback is not None:
            logger.error("%s remained invalid after repair; applying fail-closed fallback", label)
            return repaired, fallback
        raise RuntimeError(f"{label} did not return valid JSON after one repair attempt") from exc


async def process_product(job_id: str, store: PersistentStore, queue: JobQueue) -> None:
    job = await store.get_job(job_id)
    if not job or job["job_type"] != "product_generation" or job["status"] in {"completed", "cancelled", "paused", "running"}:
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

    async def checkpoint() -> bool:
        current = await store.get_product(product_id)
        if not current:
            return True
        metadata = current.get("metadata") or {}
        if current.get("status") in {"paused", "cancelled"} or bool(current.get("paused", False)) or bool(metadata.get("paused", False)):
            return True
        return False

    try:
        if await checkpoint():
            return
        await store.update_job(job_id, "running", attempts=attempts, error_message=None)
        settings = get_settings()
        gateway = build_ai_gateway(settings)
        await store.update_product(product_id, status="generating", current_stage="topic")

        strategy_prompt = (
            f"Create a concise product strategy for the digital ebook topic: {topic}. "
            "Return valid JSON with keys: positioning, audience, title, subtitle, outline "
            "(array of chapter titles)."
        )
        strategist, strategy_data = await complete_json_response(
            gateway,
            strategy_prompt,
            "You are the Hermes Pro strategist. Return only valid JSON. Do not claim market data you do not have.",
            label="strategist",
        )
        if await checkpoint():
            return

        await store.update_product(product_id, current_stage="writer")
        writer_prompt = (
            f"Using this strategy, write the ebook for topic '{topic}'. "
            f"Strategy: {json.dumps(strategy_data, ensure_ascii=False)}\n"
            "Return valid JSON with keys: introduction, chapters "
            "(array of objects with title and content), conclusion."
        )
        writer, writer_data = await complete_json_response(
            gateway,
            writer_prompt,
            "You are the Hermes Pro writer. Return only valid JSON. Produce original, useful educational content and do not fabricate citations.",
            label="writer",
        )
        if await checkpoint():
            return

        await store.update_product(product_id, current_stage="reviewer")
        review_sample = build_review_excerpt(writer_data)
        review_prompt = (
            f"Review this proposed ebook for topic '{topic}'. Assess factual accuracy, "
            "structure, completeness and readability. Return valid JSON with keys: "
            "score (integer 0-100), findings (array of strings), approved (boolean). "
            "Approval requires score >= 80. Do not infer market demand.\n"
            f"STRATEGY: {json.dumps(strategy_data, ensure_ascii=False)[:3500]}\n"
            f"REPRESENTATIVE EBOOK EXCERPTS: {review_sample}"
        )
        _, review_data = await complete_json_response(
            gateway,
            review_prompt,
            "You are the Hermes Pro reviewer. Return exactly one JSON object and be conservative: approval requires score >= 80.",
            label="reviewer",
            fallback={
                "score": 0,
                "findings": ["Reviewer output remained invalid after one repair; manual review required."],
                "approved": False,
            },
        )
        if await checkpoint():
            return

        await store.update_product(product_id, current_stage="validation")
        try:
            score = int(review_data.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        approved = bool(review_data.get("approved")) and score >= 80
        metadata = {
            "strategy": strategy_data,
            "content": writer.content,
            "content_data": writer_data,
            "review": review_data,
            "quality_score": score,
            "ai_provider": strategist.provider,
            "ai_model": strategist.model,
            "paused": False,
        }
        title = strategy_data.get("title") if isinstance(strategy_data, dict) else None
        subtitle = strategy_data.get("subtitle", "") if isinstance(strategy_data, dict) else ""

        if not approved:
            await store.update_product(product_id, status="review_required", current_stage="reviewer", title=title, metadata=metadata)
            await store.update_job(job_id, "completed", attempts=attempts)
            logger.info("product requires review job=%s product=%s score=%s", job_id, product_id, score)
            return

        await store.update_product(product_id, status="generating_artifacts", current_stage="studio", title=title, metadata=metadata)
        artifacts = build_artifacts(title or topic, subtitle, writer.content)
        artifact_urls: dict[str, str] = {}
        for kind, (path, content, content_type) in artifacts.items():
            if await checkpoint():
                return
            bucket = ARTIFACT_BUCKETS.get(kind)
            if not bucket:
                raise RuntimeError(f"No private storage bucket mapped for artifact kind: {kind}")
            storage = SupabaseStorage(settings, bucket=bucket)
            artifact_urls[kind] = await storage.upload(f"{product_id}/{path}", content, content_type)

        metadata["artifacts"] = artifact_urls
        metadata["artifact_status"] = "ready"
        await store.update_product(product_id, status="ready_to_publish", current_stage="studio", metadata=metadata)
        await store.update_job(job_id, "completed", attempts=attempts)
        logger.info("completed product_generation job=%s product=%s artifacts=%s", job_id, product_id, list(artifact_urls))
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
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=15)
    for job in await store.list_recoverable_jobs(stale_before):
        status = job.get("status")
        if status == "running":
            await store.update_job(str(job["id"]), "pending", error_message="recovered after stale worker lease")
            status = "pending"
        if status not in {"pending", "retrying"}:
            continue
        if job["job_type"] == "product_generation":
            await queue.enqueue(str(job["id"]))
        elif job["job_type"] == "agent_run":
            await queue.enqueue_agent(str(job["id"]))


async def run() -> None:
    settings = get_settings()
    store = PersistentStore(SupabaseREST(settings))
    queue = JobQueue(settings.redis_url or "redis://localhost:6379/0")
    logger.info("Hermes Pro worker started; autonomous=%s", settings.autonomy_enabled)
    loop = asyncio.get_running_loop()
    last_autonomy_tick = 0.0
    last_recovery = loop.time()
    try:
        await recover_pending(store, queue)
        while True:
            now = loop.time()
            if settings.autonomy_enabled and (now - last_autonomy_tick) >= settings.autonomy_interval_seconds:
                try:
                    outcome = await autonomy_tick(settings, store, queue)
                    logger.info("autonomy tick: %s", outcome)
                except Exception:
                    logger.exception("autonomy tick failed; worker will continue")
                last_autonomy_tick = loop.time()

            if now - last_recovery >= RECOVERY_INTERVAL_SECONDS:
                try:
                    await recover_pending(store, queue)
                except Exception:
                    logger.exception("job recovery scan failed; worker will continue")
                last_recovery = loop.time()

            agent_job_id = await queue.dequeue_agent(timeout=1)
            if agent_job_id:
                await process_agent(agent_job_id, store, settings, queue)
                continue
            job_id = await queue.dequeue(timeout=5)
            if job_id:
                await process_product(job_id, store, queue)
    finally:
        await queue.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Hermes Pro worker stopped")
