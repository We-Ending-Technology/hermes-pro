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
    while start >= 0:
        try:
            value, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    raise ValueError("AI provider response did not contain a valid JSON object")


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
