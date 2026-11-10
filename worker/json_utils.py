from __future__ import annotations

import json
from typing import Any


def parse_json_object(raw: str | None) -> dict[str, Any]:
    """Parse a JSON object from plain text or a Markdown-fenced model response."""
    if not raw or not raw.strip():
        raise ValueError("AI provider returned an empty response")

    text = raw.strip()
    decoder = json.JSONDecoder()
    start = text.find("{")
    if start < 0:
        raise ValueError("AI provider response did not contain a valid JSON object")
    try:
        value, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        # Never salvage a nested chapter object from a malformed outer manuscript.
        raise ValueError("AI provider response contained a malformed JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError("AI provider response did not contain a JSON object")
    return value


def is_ebook_payload(value: dict[str, Any]) -> bool:
    """Return True only for the full manuscript schema expected by the quality gate."""
    if not isinstance(value, dict):
        return False
    introduction = value.get("introduction")
    chapters = value.get("chapters")
    conclusion = value.get("conclusion")
    return (
        isinstance(introduction, str)
        and isinstance(chapters, list)
        and len(chapters) > 0
        and all(
            isinstance(chapter, dict)
            and isinstance(chapter.get("title"), str)
            and isinstance(chapter.get("content"), str)
            for chapter in chapters
        )
        and isinstance(conclusion, str)
    )


def build_review_excerpt(writer_data: dict[str, Any]) -> str:
    """Bound reviewer input while preserving representative content from the ebook."""
    chapters = writer_data.get("chapters")
    if not isinstance(chapters, list):
        chapters = []

    sample = {
        "introduction": str(writer_data.get("introduction") or "")[:1000],
        "chapter_count": len(chapters),
        "chapters": [
            {
                "title": str(chapter.get("title") or "")[:120],
                "content_excerpt": str(chapter.get("content") or "")[:1000],
            }
            for chapter in chapters[:6]
            if isinstance(chapter, dict)
        ],
        "conclusion": str(writer_data.get("conclusion") or "")[:1500],
    }
    return json.dumps(sample, ensure_ascii=False)
