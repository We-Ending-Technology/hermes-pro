from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.artifacts import build_artifacts
from backend.app.services.ebook_validation import validate_ebook
from backend.app.services.persistence import PersistentStore
from backend.app.services.storage import SupabaseStorage
from worker.agent_jobs import process_agent
from worker.autonomy_scheduler import autonomy_tick, supervision_tick
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



async def revise_ebook_if_needed(gateway: Any, topic: str, writer_response: Any, writer_data: dict):
    """Perform one targeted expansion pass when the first deterministic gate is short."""
    initial_gate = validate_ebook(writer_data)
    if initial_gate["approved"]:
        return writer_response, writer_data, initial_gate

    revision_prompt = (
        f"Revise and expand this ebook about '{topic}' so it passes every deterministic quality requirement. "
        "Return the COMPLETE ebook as valid JSON with keys introduction, chapters (array of title/content), conclusion. "
        "Target at least 2,200 words total, 230 words in EACH chapter, 180 words in the introduction, "
        "and 180 words in the conclusion. Preserve the useful material, add concrete steps, examples, "
        "checklists and explanations, and do not pad or repeat. Do not return a summary.\n"
        f"VALIDATION FINDINGS: {json.dumps(initial_gate, ensure_ascii=False)}\n"
        f"CURRENT EBOOK JSON: {json.dumps(writer_data, ensure_ascii=False)}"
    )
    revised_response, revised_data = await complete_json_response(
        gateway,
        revision_prompt,
        "You are the Hermes Pro developmental editor. Expand underlength sections substantively. Return only the complete valid JSON ebook.",
        label="writer_revision",
    )
    revised_gate = validate_ebook(revised_data)
    return revised_response, revised_data, revised_gate

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
            "Write a complete, practical ebook of at least 1,800 words, with 5 to 8 chapters. "
            "Each chapter must contain at least 200 substantive words; introduction and conclusion at least 150 words each. "
            "Include concrete examples, steps, checklists and original explanations; do not pad or repeat. "
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

        writer, writer_data, content_gate = await revise_ebook_if_needed(
            gateway, topic, writer, writer_data
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
        ai_review_approved = bool(review_data.get("approved")) and score >= 80
        approved = ai_review_approved and content_gate["approved"]
        combined_score = min(score, int(content_gate["score"]))
        review_findings = list(review_data.get("findings") or [])
        review_findings.extend(content_gate["findings"])
        review_data = {**review_data, "approved": approved, "findings": review_findings}
        metadata = {
            "strategy": strategy_data,
            "content": writer.content,
            "content_data": writer_data,
            "review": review_data,
            "quality_score": combined_score,
            "quality_gate": {**content_gate, "approved": approved, "ai_review_approved": ai_review_approved},
            "ai_provider": strategist.provider,
            "ai_model": strategist.model,
            "paused": False,
            "artifact_status": "not_created",
            "publication_status": "not_published",
        }
        title = strategy_data.get("title") if isinstance(strategy_data, dict) else None
        subtitle = strategy_data.get("subtitle", "") if isinstance(strategy_data, dict) else ""

        if not approved:
            await store.update_product(product_id, status="review_required", current_stage="reviewer", title=title, metadata=metadata)
            await store.update_job(job_id, "completed", attempts=attempts)
            logger.info("product requires review job=%s product=%s score=%s words=%s", job_id, product_id, combined_score, content_gate["word_count"])
            return

        await store.update_product(product_id, status="generating_artifacts", current_stage="studio", title=title, metadata=metadata)
        artifacts = build_artifacts(title or topic, subtitle, json.dumps(writer_data, ensure_ascii=False))
        expected_signatures = {"cover": bytes.fromhex("89504e470d0a1a0a"), "docx": bytes.fromhex("504b0304"), "pdf": b"%PDF-"}
        if set(artifacts) != set(expected_signatures):
            raise RuntimeError("artifact set is incomplete; expected cover, docx and pdf")
        for kind, (_, artifact_bytes, _) in artifacts.items():
            if not artifact_bytes.startswith(expected_signatures[kind]):
                raise RuntimeError("artifact validation failed for " + kind)
        artifact_urls: dict[str, str] = {}
        for kind, (path, content, content_type) in artifacts.items():
            if await checkpoint():
                return
            bucket = ARTIFACT_BUCKETS.get(kind)
            if not bucket:
                raise RuntimeError(f"No private storage bucket mapped for artifact kind: {kind}")
            storage = SupabaseStorage(settings, bucket=bucket)
            artifact_urls[kind] = await storage.upload(f"{product_id}/{path}", content, content_type)

        required_artifacts = {"cover", "docx", "pdf"}
        if set(artifact_urls) != required_artifacts:
            raise RuntimeError("not all required ebook artifacts were uploaded")
        metadata["artifacts"] = artifact_urls
        metadata["artifact_status"] = "ready"
        metadata["quality_gate"] = {**content_gate, "approved": True, "ai_review_approved": True}
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
    last_supervision_tick = 0.0
    last_heartbeat = 0.0
    last_recovery = loop.time()
    try:
        try:
            await asyncio.wait_for(recover_pending(store, queue), timeout=60)
            logger.info("initial job recovery complete")
            await queue.redis.ping()
            await store.record_worker_health("ok", "worker started; Redis PING succeeded")
            last_heartbeat = loop.time()
        except Exception:
            logger.exception("initial job recovery failed or timed out; worker will continue")
        while True:
            now = loop.time()
            if settings.autonomy_enabled and (now - last_autonomy_tick) >= settings.autonomy_interval_seconds:
                try:
                    logger.info("autonomy tick starting")
                    outcome = await asyncio.wait_for(autonomy_tick(settings, store, queue), timeout=90)
                    logger.info("autonomy tick: %s", outcome)
                except Exception:
                    logger.exception("autonomy tick failed; worker will continue")
                last_autonomy_tick = loop.time()

            if settings.autonomy_enabled and (now - last_supervision_tick) >= settings.autonomy_agent_interval_seconds:
                try:
                    outcome = await asyncio.wait_for(supervision_tick(settings, store, queue), timeout=90)
                    logger.info("autonomous chief supervision: %s", outcome)
                except Exception:
                    logger.exception("autonomous chief supervision failed; worker will continue")
                last_supervision_tick = loop.time()

            if (now - last_heartbeat) >= 30:
                try:
                    await queue.redis.ping()
                    await store.record_worker_health("ok", "worker loop alive; Redis PING succeeded")
                except Exception as exc:
                    logger.exception("worker heartbeat failed")
                    try:
                        await store.record_worker_health("error", "worker heartbeat failed: " + str(exc)[:350])
                    except Exception:
                        logger.exception("could not persist worker heartbeat failure")
                last_heartbeat = loop.time()

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
