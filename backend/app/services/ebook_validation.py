from __future__ import annotations

import re
from typing import Any

MIN_TOTAL_WORDS = 3500
MIN_CHAPTERS = 8
MIN_CHAPTER_WORDS = 300
MIN_INTRODUCTION_WORDS = 200
MIN_CONCLUSION_WORDS = 200
MIN_ILLUSTRATIONS = 4
MIN_PAGES = 10

_WORD_RE = re.compile(r"[\wÀ-ÿ]+(?:['’.-][\wÀ-ÿ]+)*", re.UNICODE)


def count_words(value: Any) -> int:
    return len(_WORD_RE.findall(str(value or "")))


def _valid_illustration(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    required = ("title", "description", "caption", "alt_text")
    if not all(isinstance(item.get(key), str) and item[key].strip() for key in required):
        return False
    steps = item.get("steps")
    return not steps or (
        isinstance(steps, list)
        and len([step for step in steps if isinstance(step, str) and step.strip()]) >= 3
    )


def validate_ebook(content_data: dict[str, Any] | None) -> dict[str, Any]:
    """Fail-closed commercial gate: editorial approval cannot override length or illustration requirements."""
    data = content_data if isinstance(content_data, dict) else {}
    raw_chapters = data.get("chapters")
    chapters = [item for item in raw_chapters if isinstance(item, dict)] if isinstance(raw_chapters, list) else []
    chapter_counts = [
        {"title": str(chapter.get("title") or ""), "words": count_words(chapter.get("content"))}
        for chapter in chapters
    ]
    intro_words = count_words(data.get("introduction"))
    conclusion_words = count_words(data.get("conclusion"))
    chapter_words = sum(item["words"] for item in chapter_counts)
    total_words = intro_words + chapter_words + conclusion_words
    raw_illustrations = data.get("illustrations")
    illustrations = [item for item in raw_illustrations if _valid_illustration(item)] if isinstance(raw_illustrations, list) else []
    illustration_count = len(illustrations)

    findings: list[str] = []
    if total_words < MIN_TOTAL_WORDS:
        findings.append(f"Conteúdo insuficiente: {total_words} palavras; mínimo {MIN_TOTAL_WORDS}.")
    if len(chapter_counts) < MIN_CHAPTERS:
        findings.append(f"Estrutura insuficiente: {len(chapter_counts)} capítulos; mínimo {MIN_CHAPTERS}.")
    short_chapters = [item for item in chapter_counts if item["words"] < MIN_CHAPTER_WORDS]
    if short_chapters:
        findings.append(f"{len(short_chapters)} capítulo(s) abaixo de {MIN_CHAPTER_WORDS} palavras.")
    if intro_words < MIN_INTRODUCTION_WORDS:
        findings.append(f"Introdução curta: {intro_words} palavras; mínimo {MIN_INTRODUCTION_WORDS}.")
    if conclusion_words < MIN_CONCLUSION_WORDS:
        findings.append(f"Conclusão curta: {conclusion_words} palavras; mínimo {MIN_CONCLUSION_WORDS}.")
    if illustration_count < MIN_ILLUSTRATIONS:
        findings.append(f"Ilustrações insuficientes: {illustration_count}; mínimo {MIN_ILLUSTRATIONS} briefs válidos.")

    approved = not findings
    length_score = min(100, round(total_words / MIN_TOTAL_WORDS * 100))
    chapter_score = min(100, round(len(chapter_counts) / MIN_CHAPTERS * 100))
    depth_score = min(
        100,
        round((chapter_words / max(1, len(chapter_counts))) / MIN_CHAPTER_WORDS * 100),
    ) if chapter_counts else 0
    intro_score = min(100, round(intro_words / MIN_INTRODUCTION_WORDS * 100))
    conclusion_score = min(100, round(conclusion_words / MIN_CONCLUSION_WORDS * 100))
    illustration_score = min(100, round(illustration_count / MIN_ILLUSTRATIONS * 100))
    score = round(
        length_score * 0.40
        + chapter_score * 0.15
        + depth_score * 0.20
        + intro_score * 0.075
        + conclusion_score * 0.075
        + illustration_score * 0.10
    )
    if not approved:
        score = min(score, 79)

    required_standard = {
        "minimum_pages": MIN_PAGES,
        "minimum_words": MIN_TOTAL_WORDS,
        "minimum_chapters": MIN_CHAPTERS,
        "minimum_chapter_words": MIN_CHAPTER_WORDS,
        "minimum_introduction_words": MIN_INTRODUCTION_WORDS,
        "minimum_conclusion_words": MIN_CONCLUSION_WORDS,
        "minimum_illustrations": MIN_ILLUSTRATIONS,
    }
    return {
        "approved": approved,
        "score": score,
        "word_count": total_words,
        "chapter_count": len(chapter_counts),
        "chapter_word_counts": chapter_counts,
        "introduction_words": intro_words,
        "conclusion_words": conclusion_words,
        "illustration_count": illustration_count,
        "minimums": required_standard,
        "required_standard": required_standard,
        "editorial_upgrade_required": not approved,
        "findings": findings,
    }
