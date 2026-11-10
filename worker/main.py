from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.artifacts import build_artifacts, validate_artifacts
from backend.app.services.ebook_validation import (
    MIN_CHAPTERS,
    MIN_CHAPTER_WORDS,
    MIN_CONCLUSION_WORDS,
    MIN_ILLUSTRATIONS,
    MIN_INTRODUCTION_WORDS,
    MIN_TOTAL_WORDS,
    validate_ebook,
)
from backend.app.services.persistence import PersistentStore
from backend.app.services.storage import SupabaseStorage
from backend.app.services.telegram import TelegramNotifier
from worker.agent_jobs import process_agent
from worker.autonomy_scheduler import autonomy_tick, supervision_tick
from worker.json_utils import build_review_excerpt, is_ebook_payload, parse_json_object

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes.worker")
MAX_ATTEMPTS = 3
RECOVERY_INTERVAL_SECONDS = 300
ARTIFACT_BUCKETS = {"cover": "covers", "docx": "exports", "pdf": "ebooks"}


async def notify_owner(settings: Any, message: str) -> None:
    """Send operational alerts when Telegram credentials are configured."""
    try:
        sent = await TelegramNotifier(settings).send(message)
        if not sent:
            logger.debug("Telegram notification skipped: integration is not configured")
    except Exception:
        logger.exception("Telegram notification failed")


async def complete_json_response(
    gateway: Any,
    prompt: str,
    system: str,
    *,
    label: str,
    fallback: dict | None = None,
    validator: Any | None = None,
):
    """Request structured JSON, repair one malformed response, and fail closed when needed."""
    result = await gateway.complete(prompt, system=system)
    def parse_result(response: Any) -> dict:
        data = parse_json_object(response.content)
        if validator is not None and not validator(data):
            raise ValueError(f"{label} response did not match its required JSON schema")
        return data

    try:
        return result, parse_result(result)
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
        return repaired, parse_result(repaired)
    except ValueError as exc:
        if fallback is not None:
            logger.error("%s remained invalid after repair; applying fail-closed fallback", label)
            return repaired, fallback
        raise RuntimeError(f"{label} did not return valid JSON after one repair attempt") from exc



async def revise_ebook_if_needed(gateway: Any, topic: str, writer_response: Any, writer_data: dict):
    """Run up to two targeted editorial passes; never approve content that misses deterministic gates."""
    best_response = writer_response
    best_data = json.loads(json.dumps(writer_data, ensure_ascii=False))
    best_gate = validate_ebook(best_data)
    if best_gate["approved"]:
        return best_response, best_data, best_gate

    def gate_key(gate: dict) -> tuple:
        return (
            bool(gate.get("approved")),
            int(gate.get("score", 0)),
            -len(gate.get("findings") or []),
            int(gate.get("word_count", 0)),
            int(gate.get("chapter_count", 0)),
            int(gate.get("illustration_count", 0)),
        )

    def valid_brief(item: Any) -> bool:
        return isinstance(item, dict) and all(
            isinstance(item.get(key), str) and item[key].strip()
            for key in ("title", "description", "caption", "alt_text")
        )

    for round_index in range(2):
        chapter_counts = best_gate.get("chapter_word_counts") or []
        needs = []
        if int(best_gate.get("word_count", 0)) < MIN_TOTAL_WORDS:
            needs.append({"section": "overall_content", "target_total_words": MIN_TOTAL_WORDS + 500})
        if int(best_gate.get("introduction_words", 0)) < MIN_INTRODUCTION_WORDS:
            needs.append({"section": "introduction", "target_words": 260})
        for index, item in enumerate(chapter_counts):
            current_words = int(item.get("words", 0))
            if current_words < MIN_CHAPTER_WORDS:
                needs.append({
                    "section": "chapter",
                    "index": index,
                    "title": item.get("title", f"Capítulo {index + 1}"),
                    "current_words": current_words,
                    "target_final_words": 380,
                    "minimum_addition_words": max(120, 380 - current_words),
                })
        missing_chapters = max(0, MIN_CHAPTERS - len(chapter_counts))
        if missing_chapters:
            needs.append({"section": "new_chapters", "count": missing_chapters, "target_words_each": 400})
        if int(best_gate.get("conclusion_words", 0)) < MIN_CONCLUSION_WORDS:
            needs.append({"section": "conclusion", "target_words": 260})
        if int(best_gate.get("illustration_count", 0)) < MIN_ILLUSTRATIONS:
            needs.append({"section": "illustrations", "count": MIN_ILLUSTRATIONS})

        prompt = (
            f"Rodada editorial {round_index + 1} para o ebook sobre '{topic}'. "
            "Amplie o manuscrito sem reescrever, resumir ou remover conteúdo existente. "
            "Retorne SOMENTE JSON válido com as chaves: introduction_addition (string), "
            "chapter_additions (array de objetos {index, content}), new_chapters "
            "(array de objetos {title, content}), conclusion_addition (string) e illustrations "
            "(array de objetos {title, description, caption, alt_text, chapter_index, steps}). "
            "REGRA CRÍTICA: cada capítulo listado em needs deve terminar com pelo menos 380 palavras. "
            "A adição de cada capítulo deve conter, no mínimo, o número de palavras indicado em minimum_addition_words; "
            "não devolva um parágrafo curto. O manuscrito final deve ter pelo menos 4.000 palavras, "
            "8 capítulos completos e quatro briefs de ilustração específicos do tema. "
            "Use exemplos, procedimentos, checklists, critérios de decisão e aplicações reais. "
            "Não invente fontes, estatísticas, pesquisas ou resultados de mercado. "
            f"PENDÊNCIAS EXATAS: {json.dumps(needs, ensure_ascii=False)}\n"
            f"MANUSCRITO ATUAL: {json.dumps(best_data, ensure_ascii=False)}"
        )
        try:
            revision_response, additions = await complete_json_response(
                gateway,
                prompt,
                "Você é editor técnico rigoroso. Retorne apenas o JSON de complementos solicitado, sem markdown e sem texto externo.",
                label=f"writer_revision_round_{round_index + 1}",
            )
        except Exception as exc:
            logger.warning("ebook revision round %s failed: %s", round_index + 1, str(exc)[:240])
            break

        if not isinstance(additions, dict):
            continue

        merged = json.loads(json.dumps(best_data, ensure_ascii=False))
        intro_addition = additions.get("introduction_addition")
        if isinstance(intro_addition, str) and intro_addition.strip():
            merged["introduction"] = (str(merged.get("introduction", "")).rstrip() + "\n\n" + intro_addition.strip()).strip()

        conclusion_addition = additions.get("conclusion_addition")
        if isinstance(conclusion_addition, str) and conclusion_addition.strip():
            merged["conclusion"] = (str(merged.get("conclusion", "")).rstrip() + "\n\n" + conclusion_addition.strip()).strip()

        chapter_additions = additions.get("chapter_additions")
        if isinstance(chapter_additions, list):
            chapters = merged.get("chapters")
            if isinstance(chapters, list):
                for item in chapter_additions:
                    if not isinstance(item, dict):
                        continue
                    index = item.get("index")
                    addition = item.get("content")
                    if isinstance(index, int) and 0 <= index < len(chapters) and isinstance(addition, str) and addition.strip():
                        existing = str(chapters[index].get("content", "")).rstrip()
                        chapters[index]["content"] = (existing + "\n\n" + addition.strip()).strip()

        new_chapters = additions.get("new_chapters")
        if isinstance(new_chapters, list):
            chapters = merged.setdefault("chapters", [])
            existing_titles = {
                str(chapter.get("title") or "").strip().casefold()
                for chapter in chapters if isinstance(chapter, dict)
            }
            for chapter in new_chapters:
                if len(chapters) >= MIN_CHAPTERS:
                    break
                if not isinstance(chapter, dict):
                    continue
                title_value = str(chapter.get("title") or "").strip()
                content_value = str(chapter.get("content") or "").strip()
                if not title_value or not content_value or title_value.casefold() in existing_titles:
                    continue
                chapters.append({"title": title_value, "content": content_value})
                existing_titles.add(title_value.casefold())

        existing_illustrations = [
            item for item in merged.get("illustrations", [])
            if valid_brief(item)
        ] if isinstance(merged.get("illustrations"), list) else []
        new_illustrations = additions.get("illustrations")
        if isinstance(new_illustrations, list):
            existing_illustrations.extend(item for item in new_illustrations if valid_brief(item))
        merged["illustrations"] = existing_illustrations[:MIN_ILLUSTRATIONS]

        revised_gate = validate_ebook(merged)
        if gate_key(revised_gate) > gate_key(best_gate):
            best_response = revision_response
            best_data = merged
            best_gate = revised_gate
        if best_gate["approved"]:
            return best_response, best_data, best_gate

    return best_response, best_data, best_gate

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

    settings = get_settings()
    try:
        if await checkpoint():
            return
        await store.update_job(job_id, "running", attempts=attempts, error_message=None)
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
            "Write a complete, practical ebook of at least 3,500 words, with 8 to 10 chapters. "
            "Each chapter must contain at least 300 substantive words; introduction and conclusion at least 200 words each. "
            "Include concrete examples, step-by-step procedures, checklists, templates and original explanations; do not pad or repeat. "
            "Create at least four original, topic-specific illustration briefs, each with title, description, caption, alt_text, chapter_index and 3-4 practical steps. "
            "Return valid JSON with keys: introduction, chapters (array of objects with title and content), conclusion, illustrations."
        )
        writer, writer_data = await complete_json_response(
            gateway,
            writer_prompt,
            "You are the Hermes Pro writer. Return only valid JSON. Produce original, useful educational content and do not fabricate citations.",
            label="writer",
            validator=is_ebook_payload,
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
            f"Review this proposed ebook for topic '{topic}'. Assess factual accuracy, structure, depth, completeness, readability and whether its illustration briefs are useful and specific. "
            "The commercial gate requires at least 3,500 words, 8 chapters, 4 internal illustrations, and a final PDF of at least 10 pages. "
            "Return valid JSON with keys: score (integer 0-100), findings (array of strings), approved (boolean). "
            "Do not approve superficial, repetitive or unsupported content. Do not infer market demand.\n"
            f"STRATEGY: {json.dumps(strategy_data, ensure_ascii=False)[:3500]}\n"
            f"REPRESENTATIVE EBOOK EXCERPTS: {review_sample}\n"
            f"ILLUSTRATION BRIEFS: {json.dumps(writer_data.get('illustrations', []), ensure_ascii=False)[:2500]}"
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
            pending = "; ".join(content_gate.get("findings") or []) or "revisão editorial"
            await notify_owner(settings, f"Hermes Pro: produto bloqueado para revisão. Tema: {topic}. Palavras: {content_gate['word_count']}. Pendências: {pending}.")
            return

        await store.update_product(product_id, status="generating_artifacts", current_stage="studio", title=title, metadata=metadata)
        artifacts = build_artifacts(title or topic, subtitle, json.dumps(writer_data, ensure_ascii=False))
        artifact_gate = validate_artifacts(artifacts)
        if not artifact_gate["approved"]:
            raise RuntimeError("artifact quality gate failed: " + "; ".join(artifact_gate.get("findings") or []))
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
        metadata["quality_gate"] = {**content_gate, **artifact_gate, "approved": True, "ai_review_approved": True}
        metadata["artifact_validation"] = artifact_gate
        await store.update_product(product_id, status="ready_to_publish", current_stage="studio", metadata=metadata)
        await store.update_job(job_id, "completed", attempts=attempts)
        logger.info("completed product_generation job=%s product=%s artifacts=%s pages=%s illustrations=%s", job_id, product_id, list(artifact_urls), artifact_gate["page_count"], artifact_gate["illustration_count"])
        await notify_owner(settings, f"Hermes Pro: ebook pronto para publicação (ainda não publicado). Produto: {title or topic}. {content_gate['word_count']} palavras, {artifact_gate['page_count']} páginas, {artifact_gate['illustration_count']} ilustrações.")
    except Exception as exc:
        message = str(exc)[:1000]
        if attempts < MAX_ATTEMPTS:
            await store.update_job(job_id, "retrying", attempts=attempts, error_message=message)
            delay = min(60, 5 * (2 ** (attempts - 1)))
            logger.warning("product retry scheduled job=%s attempt=%s delay_seconds=%s", job_id, attempts, delay)
            await asyncio.sleep(delay)
            await queue.enqueue(job_id)
        else:
            await store.update_job(job_id, "failed", attempts=attempts, error_message=message)
            await store.update_product(product_id, status="failed")
            await notify_owner(settings, f"Hermes Pro: falha definitiva na geração do produto {topic}. Tentativas: {attempts}. Erro: {message[:300]}")
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
