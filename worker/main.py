from __future__ import annotations

import asyncio
import ctypes
import gc
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import get_settings
from backend.app.db.supabase import SupabaseREST
from backend.app.queue import JobQueue
from backend.app.services.artifacts import (build_docx_artifact, build_pdf_artifact, prepare_artifact_context, validate_artifacts)
from backend.app.services.ai_images import generate_cover_artwork
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
ARTIFACT_RENDER_SEMAPHORE = asyncio.Semaphore(1)
MAX_ATTEMPTS = 3
RECOVERY_INTERVAL_SECONDS = 10  # Keep orphan detection within the 90-second lease window
ARTIFACT_BUCKETS = {"cover": "covers", "docx": "exports", "pdf": "ebooks"}


def _container_memory_bytes() -> int | None:
    """Read cgroup-v2 memory usage when available; never fail the worker on telemetry."""
    try:
        return int(Path("/sys/fs/cgroup/memory.current").read_text().strip())
    except (OSError, ValueError):
        return None


def _release_worker_memory(label: str) -> None:
    """Collect released Python objects and ask glibc to return free arenas to the OS."""
    collected = gc.collect()
    trimmed = 0
    try:
        libc = ctypes.CDLL("libc.so.6")
        malloc_trim = libc.malloc_trim
        malloc_trim.argtypes = [ctypes.c_size_t]
        malloc_trim.restype = ctypes.c_int
        trimmed = int(malloc_trim(0))
    except (OSError, AttributeError):
        pass
    memory = _container_memory_bytes()
    logger.info(
        "worker memory cleanup label=%s gc_collected=%s malloc_trim=%s memory_mib=%s",
        label,
        collected,
        trimmed,
        round(memory / (1024 * 1024), 1) if memory is not None else "unknown",
    )


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



def is_marketing_pack_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    description = value.get("product_description")
    short_description = value.get("short_description")
    benefits = value.get("benefits")
    faq = value.get("faq")
    keywords = value.get("keywords")
    social_posts = value.get("social_posts")
    if not isinstance(description, str) or len(description.strip()) < 300:
        return False
    if not isinstance(short_description, str) or len(short_description.strip()) < 80:
        return False
    if not isinstance(value.get("target_audience"), str) or len(value["target_audience"].strip()) < 20:
        return False
    contents = value.get("contents")
    if not isinstance(contents, list) or len(contents) < 5:
        return False
    if not isinstance(benefits, list) or len(benefits) < 4 or not all(isinstance(item, str) and item.strip() for item in benefits[:4]):
        return False
    if not isinstance(faq, list) or len(faq) < 3 or not all(
        isinstance(item, dict)
        and isinstance(item.get("question"), str) and item["question"].strip()
        and isinstance(item.get("answer"), str) and item["answer"].strip()
        for item in faq[:3]
    ):
        return False
    if not isinstance(keywords, list) or len(keywords) < 5 or not all(isinstance(item, str) and item.strip() for item in keywords[:5]):
        return False
    if not isinstance(social_posts, list) or len(social_posts) < 3:
        return False
    if not all(
        isinstance(item, dict)
        and all(isinstance(item.get(key), str) and item[key].strip() for key in ("platform", "hook", "caption", "cta"))
        for item in social_posts[:3]
    ):
        return False
    full_text = json.dumps(value, ensure_ascii=False).casefold()
    prohibited_claims = ("renda garantida", "ganho garantido", "resultado garantido", "fique rico", "lucro garantido")
    return not any(claim in full_text for claim in prohibited_claims)


async def revise_ebook_if_needed(gateway: Any, topic: str, writer_response: Any, writer_data: dict):
    """Run up to two targeted editorial passes; never approve content that misses deterministic gates."""
    best_response = writer_response
    best_gate = validate_ebook(writer_data)
    if best_gate["approved"]:
        return best_response, writer_data, best_gate
    best_data = json.loads(json.dumps(writer_data, ensure_ascii=False))

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

def normalize_review_result(review_data: dict, content_gate: dict) -> dict:
    """Do not let an AI reviewer veto deterministic checks it cannot measure reliably."""
    result = dict(review_data or {})
    findings = [str(item) for item in (result.get("findings") or []) if str(item).strip()]
    metric_terms = (
        "palavra", "word count", "página", "pagina", "page", "capítulo", "capitulo",
        "chapter", "ilustra", "brief", "contagem", "extensão", "extensao", "mínimo",
        "minimo", "minimum", "quantidade", "número de",
    )
    substantive_terms = (
        "superficial", "genérico", "generico", "repetitivo", "impreciso", "incorreto",
        "inconsistente", "confuso", "plágio", "plagio", "sem exemplo", "sem exemplos",
        "não explica", "nao explica", "não aprofunda", "nao aprofunda", "contraditório",
        "contraditorio", "desatualizado", "falso", "inventado", "pouco útil", "pouco util",
    )
    metric_only, substantive, positive = [], [], []
    for finding in findings:
        lowered = finding.casefold()
        has_metric = any(term in lowered for term in metric_terms)
        has_substantive = any(term in lowered for term in substantive_terms)
        has_negative = any(term in lowered for term in (
            "contudo", "porém", "porem", "abaixo", "carece", "insuficiente", "falta",
            "não atende", "nao atende", "não cumpre", "nao cumpre", "reprov",
        ))
        if has_metric and has_negative and not has_substantive:
            metric_only.append(finding)
        elif has_negative or has_substantive:
            substantive.append(finding)
        else:
            positive.append(finding)

    if content_gate.get("approved") and metric_only and not substantive:
        try:
            score = int(result.get("score") or 0)
        except (TypeError, ValueError):
            score = 0
        result.update({
            "approved": True,
            "score": max(90, score),
            "findings": [],
            "positive_findings": positive,
            "ignored_metric_findings": metric_only,
            "approval_basis": "deterministic_content_gate_passed; AI rejection concerned only verified metrics",
        })
    return result


def build_product_metadata(
    existing_metadata: dict | None,
    *,
    strategy_data: dict,
    content: str,
    content_data: dict,
    review_data: dict,
    quality_score: int,
    content_gate: dict,
    ai_review_approved: bool,
    approved: bool,
    ai_provider: str,
    ai_model: str,
) -> dict:
    """Merge generated content into existing metadata without dropping rebuild history or archived files."""
    metadata = dict(existing_metadata or {})
    metadata.update({
        "strategy": strategy_data,
        "content": content,
        "content_data": content_data,
        "review": review_data,
        "quality_score": quality_score,
        "quality_gate": {**content_gate, "approved": approved, "ai_review_approved": ai_review_approved},
        "ai_provider": ai_provider,
        "ai_model": ai_model,
        "paused": False,
        "artifact_status": "revision_required",
    })
    metadata.setdefault("publication_status", "not_published")
    return metadata


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
        await store.update_product(product_id, status="generating", current_stage="create_outline")

        payload = job.get("payload") or {}
        reuse_existing_content = bool(payload.get("reuse_existing_content"))
        current_product = await store.get_product(product_id) or {}
        existing_metadata = dict(current_product.get("metadata") or {})

        if reuse_existing_content:
            strategy_data = existing_metadata.get("strategy") or {}
            writer_data = existing_metadata.get("content_data")
            writer_content = str(existing_metadata.get("content") or "")
            if not isinstance(writer_data, dict) or not writer_content:
                raise ValueError("existing ebook content is unavailable for validation-only job")
            content_gate = validate_ebook(writer_data)
            if not content_gate.get("approved"):
                raise ValueError("existing ebook no longer passes deterministic content validation")
            ai_provider = str(existing_metadata.get("ai_provider") or settings.ai_provider)
            ai_model = str(existing_metadata.get("ai_model") or settings.gemini_model)
            await store.update_product(product_id, current_stage="review_content")
            review_data = normalize_review_result(existing_metadata.get("review") or {}, content_gate)
            if not review_data.get("approved"):
                gateway = build_ai_gateway(settings)
                review_sample = build_review_excerpt(writer_data)
                review_prompt = (
                    f"Review the editorial quality of this ebook about '{topic}'. "
                    "Do NOT evaluate word count, page count, chapter count or illustration quantity; "
                    "those are checked by deterministic software gates. Evaluate only factual accuracy, "
                    "coherence, practical usefulness, originality, repetition, unsupported claims and clarity. "
                    "Reject only for a substantive editorial defect, not for a metric that the software has already verified. "
                    "Return JSON with score (0-100), findings (array of strings), approved (boolean). "
                    f"STRATEGY: {json.dumps(strategy_data, ensure_ascii=False)[:3500]}\n"
                    f"EXCERPTS: {review_sample}\n"
                    f"ILLUSTRATIONS: {json.dumps(writer_data.get('illustrations', []), ensure_ascii=False)[:2500]}"
                )
                _, review_data = await complete_json_response(
                    gateway,
                    review_prompt,
                    "You are the Hermes Pro editorial reviewer. Ignore measurable counts; inspect only substantive content quality.",
                    label="reviewer_validation",
                    fallback={"score": 0, "findings": ["Editorial review unavailable; manual review required."], "approved": False},
                )
                review_data = normalize_review_result(review_data, content_gate)
        else:
            await store.update_product(product_id, current_stage="create_outline")
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

            await store.update_product(product_id, current_stage="generate_content")
            writer_prompt = (
                f"Using this strategy, write the ebook for topic '{topic}'. "
                f"Strategy: {json.dumps(strategy_data, ensure_ascii=False)}\n"
                "Write a complete, practical ebook targeting at least 4,000 words, with 8 to 10 chapters. "
                "Each chapter must contain at least 350 substantive words; introduction and conclusion at least 250 words each. "
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
            writer_content = writer.content
            ai_provider = strategist.provider
            ai_model = strategist.model

            await store.update_product(product_id, current_stage="reviewer")
            review_sample = build_review_excerpt(writer_data)
            review_prompt = (
                f"Review the editorial quality of this ebook about '{topic}'. "
                "Do NOT evaluate word count, page count, chapter count or illustration quantity; "
                "those are checked by deterministic software gates. Evaluate only factual accuracy, "
                "coherence, practical usefulness, originality, repetition, unsupported claims and clarity. "
                "Reject only for a substantive editorial defect, not for a metric that the software has already verified. "
                "Return JSON with score (0-100), findings (array of strings), approved (boolean). "
                "Do not infer market demand.\n"
                f"STRATEGY: {json.dumps(strategy_data, ensure_ascii=False)[:3500]}\n"
                f"EXCERPTS: {review_sample}\n"
                f"ILLUSTRATIONS: {json.dumps(writer_data.get('illustrations', []), ensure_ascii=False)[:2500]}"
            )
            _, review_data = await complete_json_response(
                gateway,
                review_prompt,
                "You are the Hermes Pro editorial reviewer. Ignore measurable counts; inspect only substantive content quality.",
                label="reviewer",
                fallback={
                    "score": 0,
                    "findings": ["Reviewer output remained invalid after one repair; manual review required."],
                    "approved": False,
                },
            )
            review_data = normalize_review_result(review_data, content_gate)

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
        current_product = await store.get_product(product_id) or {}
        metadata = build_product_metadata(
            current_product.get("metadata"),
            strategy_data=strategy_data,
            content=writer_content,
            content_data=writer_data,
            review_data=review_data,
            quality_score=combined_score,
            content_gate=content_gate,
            ai_review_approved=ai_review_approved,
            approved=approved,
            ai_provider=ai_provider,
            ai_model=ai_model,
        )
        title = strategy_data.get("title") if isinstance(strategy_data, dict) else None
        subtitle = strategy_data.get("subtitle", "") if isinstance(strategy_data, dict) else ""

        if not approved:
            await store.update_product(product_id, status="review_required", current_stage="reviewer", title=title, metadata=metadata)
            await store.update_job(job_id, "completed", attempts=attempts)
            logger.info("product requires review job=%s product=%s score=%s words=%s", job_id, product_id, combined_score, content_gate["word_count"])
            pending = "; ".join(content_gate.get("findings") or []) or "revisão editorial"
            await notify_owner(settings, f"Hermes Pro: produto bloqueado para revisão. Tema: {topic}. Palavras: {content_gate['word_count']}. Pendências: {pending}.")
            return

        if not is_marketing_pack_payload(metadata.get("marketing_pack")):
            await store.update_product(product_id, status="generating", current_stage="publication", title=title, metadata=metadata)
            chapter_titles = [
                str(item.get("title", "")).strip()
                for item in (writer_data.get("chapters") or [])[:10]
                if isinstance(item, dict) and item.get("title")
            ]
            marketing_prompt = (
                f"Prepare a truthful commercial listing and launch content for the ebook '{title or topic}'. "
                f"Subtitle: {subtitle}. Strategy: {json.dumps(strategy_data, ensure_ascii=False)[:2500]}. "
                f"Chapter outline: {json.dumps(chapter_titles, ensure_ascii=False)}. "
                "Return ONLY JSON with: product_description (300-500 words, Brazilian Portuguese), "
                "short_description (80-120 words), target_audience (specific audience), "
                "benefits (5 concrete benefits), contents (array of 6-10 included items), "
                "faq (4 objects with question and answer), keywords (8 search terms), "
                "social_posts (3 objects with platform, hook, caption and cta for Instagram, TikTok and Facebook). "
                "Use persuasive but honest copy. Never promise income, sales, results, employment, health outcomes, "
                "or guaranteed success. Do not invent testimonials, research, statistics, credentials, discounts, "
                "bonuses, guarantees, or features not present in the manuscript. Do not invent price or checkout URL. "
                "Explain clearly what the buyer receives and who benefits from the guide."
            )
            _, marketing_pack = await complete_json_response(
                gateway,
                marketing_prompt,
                "You are a careful Brazilian digital-product copywriter. Create accurate sales copy from the supplied book facts only. Return valid JSON and no Markdown.",
                label="commercial_marketing_pack",
                validator=is_marketing_pack_payload,
            )
            metadata["marketing_pack"] = marketing_pack
            metadata["marketing_pack_status"] = "ready"

        await store.update_product(product_id, status="generating_artifacts", current_stage="generate_cover", title=title, metadata=metadata)
        cover_artwork = None
        cover_art_metadata = {
            "provider": "local_vector",
            "model": None,
            "generated": False,
        }
        image_provider = str(settings.ai_image_provider or "aihorde").strip().lower()
        if image_provider in {"ovhcloud", "aihorde"}:
            cover_artwork = await generate_cover_artwork(title or topic, subtitle, writer_data, settings)
            if image_provider == "ovhcloud":
                cover_art_metadata = {
                    "provider": "ovhcloud",
                    "model": settings.ovhcloud_image_model,
                    "generated": True,
                    "license_basis": "Stable Diffusion XL 1.0; CreativeML OpenRAIL++-M; commercial use subject to license restrictions",
                }
            else:
                cover_art_metadata = {
                    "provider": "ai_horde",
                    "model": settings.ai_horde_model,
                    "generated": True,
                    "license_basis": "Stable Diffusion 2.1; CreativeML OpenRAIL++-M; commercial use subject to license restrictions",
                }
        elif settings.ai_image_required:
            raise RuntimeError("AI_IMAGE_REQUIRED is enabled but AI_IMAGE_PROVIDER is not configured for a supported image provider")

        if settings.ai_image_required and not cover_artwork:
            raise RuntimeError("commercial publication requires a successfully generated AI cover")

        logger.info(
            "AI cover generated product=%s provider=%s bytes=%s",
            product_id,
            cover_art_metadata["provider"],
            len(cover_artwork or b""),
        )
        logger.info("artifact rendering queued product=%s", product_id)
        async with ARTIFACT_RENDER_SEMAPHORE:
            artifact_context = await asyncio.to_thread(
                prepare_artifact_context,
                title or topic,
                subtitle,
                json.dumps(writer_data, ensure_ascii=False),
                cover_artwork,
            )
            await store.update_product(product_id, current_stage="generate_pdf")
            pdf_artifact = await asyncio.to_thread(
                build_pdf_artifact, title or topic, subtitle, artifact_context
            )
            await store.update_product(product_id, current_stage="generate_docx")
            docx_artifact = await asyncio.to_thread(
                build_docx_artifact, title or topic, subtitle, artifact_context
            )
            artifacts = {
                "cover": (f"{artifact_context['slug']}/cover.png", artifact_context["cover"], "image/png"),
                "pdf": pdf_artifact,
                "docx": docx_artifact,
            }
            await store.update_product(product_id, current_stage="validate_files")
            artifact_gate = await asyncio.to_thread(validate_artifacts, artifacts)
        logger.info(
            "artifact rendering completed product=%s artifacts=%s pages=%s illustrations=%s",
            product_id,
            list(artifacts),
            artifact_gate["page_count"],
            artifact_gate["illustration_count"],
        )
        if not artifact_gate["approved"]:
            raise RuntimeError("artifact quality gate failed: " + "; ".join(artifact_gate.get("findings") or []))
        expected_signatures = {"cover": bytes.fromhex("89504e470d0a1a0a"), "docx": bytes.fromhex("504b0304"), "pdf": b"%PDF-"}
        if set(artifacts) != set(expected_signatures):
            raise RuntimeError("artifact set is incomplete; expected cover, docx and pdf")
        for kind, (_, artifact_bytes, _) in artifacts.items():
            if not artifact_bytes.startswith(expected_signatures[kind]):
                raise RuntimeError("artifact validation failed for " + kind)
        artifact_urls: dict[str, str] = {}
        artifact_paths: dict[str, dict[str, str]] = {}
        for kind, (path, content, content_type) in artifacts.items():
            if await checkpoint():
                return
            bucket = ARTIFACT_BUCKETS.get(kind)
            if not bucket:
                raise RuntimeError(f"No private storage bucket mapped for artifact kind: {kind}")
            storage = SupabaseStorage(settings, bucket=bucket)
            object_path = f"{product_id}/{path}"
            logger.info("artifact upload started product=%s kind=%s", product_id, kind)
            artifact_urls[kind] = await storage.upload(object_path, content, content_type)
            artifact_paths[kind] = {"bucket": bucket, "path": object_path}
            logger.info("artifact upload completed product=%s kind=%s", product_id, kind)

        required_artifacts = {"cover", "docx", "pdf"}
        if set(artifact_urls) != required_artifacts:
            raise RuntimeError("not all required ebook artifacts were uploaded")
        metadata["artifacts"] = artifact_urls
        metadata["artifact_paths"] = artifact_paths
        metadata["artifact_urls_expires_at"] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        metadata["artifact_status"] = "ready"
        metadata["cover_art"] = cover_art_metadata
        metadata["quality_gate"] = {
            **content_gate,
            **artifact_gate,
            "approved": True,
            "ai_review_approved": True,
            "ai_cover_generated": bool(cover_artwork),
        }
        metadata["artifact_validation"] = artifact_gate
        publication_ready = bool(cover_artwork)
        final_status = "ready_to_publish" if publication_ready else "review_required"
        if publication_ready:
            offer_draft = await store.ensure_offer_draft(product_id)
            metadata["offer_draft_id"] = offer_draft.get("id")
            metadata["offer_status"] = "draft_pending_human_price_and_checkout"
        await store.update_product(
            product_id,
            status=final_status,
            current_stage="commercial_offer" if publication_ready else "generate_cover",
            metadata=metadata,
        )
        await store.update_job(job_id, "completed", attempts=attempts)
        logger.info(
            "completed product_generation job=%s product=%s status=%s cover_provider=%s pages=%s illustrations=%s",
            job_id,
            product_id,
            final_status,
            cover_art_metadata["provider"],
            artifact_gate["page_count"],
            artifact_gate["illustration_count"],
        )
        if publication_ready:
            await notify_owner(settings, f"Hermes Pro: ebook pronto para publicação (ainda não publicado). Produto: {title or topic}. Capa AI: {cover_art_metadata['model']}. {content_gate['word_count']} palavras, {artifact_gate['page_count']} páginas, {artifact_gate['illustration_count']} ilustrações.")
        else:
            await notify_owner(settings, f"Hermes Pro: arquivos gerados, mas publicação bloqueada porque a capa de IA não foi gerada. Produto: {title or topic}.")
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
            try:
                current_product = await store.get_product(product_id) or {}
                failure_metadata = dict(current_product.get("metadata") or {})
                failure_metadata["artifact_status"] = "revision_required"
                failure_metadata.setdefault("publication_status", "not_published")
                failure_gate = dict(failure_metadata.get("quality_gate") or {})
                failure_gate["approved"] = False
                failure_metadata["quality_gate"] = failure_gate
                await store.update_product(product_id, status="failed", metadata=failure_metadata)
            except Exception:
                logger.exception("failed to persist product rebuild state after terminal failure")
            await notify_owner(settings, f"Hermes Pro: falha definitiva na geração do produto {topic}. Tentativas: {attempts}. Erro: {message[:300]}")
        logger.exception("product_generation failed job=%s", job_id)


async def recover_pending(store: PersistentStore, queue: JobQueue) -> None:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=90)
    recovered = 0
    for job in await store.list_recoverable_jobs(stale_before):
        status = job.get("status")
        if status == "running":
            await store.update_job(str(job["id"]), "retrying", error_message="recovered after stale worker lease (>90s)")
            await queue.remove_processing(str(job["id"]), agent=job.get("job_type") == "agent_run")
            status = "retrying"
        if status not in {"pending", "retrying"}:
            continue
        if job["job_type"] == "product_generation":
            await queue.enqueue(str(job["id"]))
            recovered += 1
        elif job["job_type"] == "agent_run":
            await queue.enqueue_agent(str(job["id"]))
            recovered += 1

    try:
        depths = await queue.depths()
    except Exception:
        depths = {"product": "unknown", "agent": "unknown"}
    logger.info("job recovery scan complete recovered=%s queue_depths=%s", recovered, depths)


async def _job_heartbeat(store: PersistentStore, job_id: str, stop: asyncio.Event) -> None:
    """Refresh a running job lease every 30 seconds independently of its long task."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except asyncio.TimeoutError:
            try:
                await store.touch_job(job_id)
                await store.record_worker_health("ok", f"worker active job={job_id}")
            except Exception:
                logger.exception("job heartbeat failed job=%s", job_id)


async def _run_job_with_lease(store: PersistentStore, queue: JobQueue, job_id: str, *, agent: bool) -> None:
    stop = asyncio.Event()
    heartbeat = asyncio.create_task(_job_heartbeat(store, job_id, stop))
    try:
        if agent:
            await process_agent(job_id, store, get_settings(), queue)
        else:
            await process_product(job_id, store, queue)
    finally:
        stop.set()
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)
        try:
            job = await store.get_job(job_id)
            if job and job.get("status") == "failed":
                await queue.dead_letter(job_id, agent=agent, reason=job.get("error_message") or "max_attempts_exceeded")
            else:
                await queue.ack(job_id, agent=agent)
        except Exception:
            logger.exception("failed to acknowledge/dead-letter job=%s", job_id)


async def run() -> None:
    settings = get_settings()
    store = PersistentStore(SupabaseREST(settings))
    queue = JobQueue(settings.redis_url or "redis://localhost:6379/0")
    logger.info("Hermes Pro worker started; autonomous=%s", settings.autonomy_enabled)
    loop = asyncio.get_running_loop()
    last_autonomy_tick = 0.0
    last_supervision_tick = 0.0
    last_heartbeat = 0.0
    last_memory_cleanup = loop.time()
    last_recovery = loop.time()
    try:
        try:
            await asyncio.wait_for(recover_pending(store, queue), timeout=60)
            logger.info("initial job recovery complete")
            await queue.redis.ping()
            depths = await queue.depths()
            await store.record_worker_health(
                "ok",
                f"worker started; Redis PING succeeded; product_queue={depths['product']}; agent_queue={depths['agent']}",
            )
            last_heartbeat = loop.time()
        except Exception:
            logger.exception("initial job recovery failed or timed out; worker will continue")
        while True:
            now = loop.time()
            if (now - last_memory_cleanup) >= 60:
                _release_worker_memory("periodic")
                last_memory_cleanup = loop.time()

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
                    depths = await queue.depths()
                    await store.record_worker_health(
                        "ok",
                        f"worker loop alive; Redis PING succeeded; product_queue={depths['product']}; agent_queue={depths['agent']}",
                    )
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
                logger.info("dequeued agent job=%s", agent_job_id)
                try:
                    await _run_job_with_lease(store, queue, agent_job_id, agent=True)
                finally:
                    _release_worker_memory("agent")
                continue
            job_id = await queue.dequeue(timeout=5)
            if job_id:
                logger.info("dequeued product job=%s", job_id)
                try:
                    await _run_job_with_lease(store, queue, job_id, agent=False)
                finally:
                    _release_worker_memory("product")
    finally:
        await queue.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Hermes Pro worker stopped")
