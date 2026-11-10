from __future__ import annotations

import re
from typing import Any

MIN_TOTAL_WORDS = 1800
MIN_CHAPTERS = 5
MIN_CHAPTER_WORDS = 200
MIN_INTRODUCTION_WORDS = 150
MIN_CONCLUSION_WORDS = 150

_WORD_RE = re.compile(r"[\wÀ-ÿ]+(?:['’.-][\wÀ-ÿ]+)*", re.UNICODE)


def count_words(value: Any) -> int:
    return len(_WORD_RE.findall(str(value or "")))


def validate_ebook(content_data: dict[str, Any] | None) -> dict[str, Any]:
    """Deterministic commercial-length gate; LLM approval cannot override it."""
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

    findings: list[str] = []
    if total_words < MIN_TOTAL_WORDS:
        findings.append(f"Conteúdo insuficiente: {total_words} palavras; mínimo {MIN_TOTAL_WORDS}.")
    if len(chapter_counts) < MIN_CHAPTERS:
        findings.append(f"Estrutura insuficiente: {len(chapter_counts)} capítulos; mínimo {MIN_CHAPTERS}.")
    short_chapters = [item for item in chapter_counts if item["words"] < MIN_CHAPTER_WORDS]
    if short_chapters:
        findings.append(
            f"{len(short_chapters)} capítulo(s) abaixo de {MIN_CHAPTER_WORDS} palavras."
        )
    if intro_words < MIN_INTRODUCTION_WORDS:
        findings.append(
            f"Introdução curta: {intro_words} palavras; mínimo {MIN_INTRODUCTION_WORDS}."
        )
    if conclusion_words < MIN_CONCLUSION_WORDS:
        findings.append(
            f"Conclusão curta: {conclusion_words} palavras; mínimo {MIN_CONCLUSION_WORDS}."
        )

    approved = not findings
    length_score = min(100, round(total_words / MIN_TOTAL_WORDS * 100))
    chapter_score = min(100, round(len(chapter_counts) / MIN_CHAPTERS * 100))
    depth_score = min(
        100,
        round((sum(item["words"] for item in chapter_counts) / max(1, len(chapter_counts))) / MIN_CHAPTER_WORDS * 100),
    ) if chapter_counts else 0
    intro_score = min(100, round(intro_words / MIN_INTRODUCTION_WORDS * 100))
    conclusion_score = min(100, round(conclusion_words / MIN_CONCLUSION_WORDS * 100))
    score = round(
        length_score * 0.50
        + chapter_score * 0.20
        + depth_score * 0.15
        + intro_score * 0.075
        + conclusion_score * 0.075
    )
    if not approved:
        score = min(score, 79)

    return {
        "approved": approved,
        "score": score,
        "word_count": total_words,
        "chapter_count": len(chapter_counts),
        "chapter_word_counts": chapter_counts,
        "introduction_words": intro_words,
        "conclusion_words": conclusion_words,
        "minimums": {
            "total_words": MIN_TOTAL_WORDS,
            "chapters": MIN_CHAPTERS,
            "chapter_words": MIN_CHAPTER_WORDS,
            "introduction_words": MIN_INTRODUCTION_WORDS,
            "conclusion_words": MIN_CONCLUSION_WORDS,
        },
        "findings": findings,
    }
