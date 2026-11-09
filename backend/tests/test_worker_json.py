import pytest

from worker.json_utils import build_review_excerpt, parse_json_object


def test_parse_json_object_accepts_markdown_fence_and_surrounding_text():
    parsed = parse_json_object('Resultado:\n```json\n{"score": 91, "approved": true}\n```')

    assert parsed == {"score": 91, "approved": True}


def test_parse_json_object_rejects_empty_provider_response():
    with pytest.raises(ValueError, match="empty response"):
        parse_json_object("  ")


def test_build_review_excerpt_bounds_large_chapter_content():
    writer = {
        "introduction": "i" * 5000,
        "chapters": [{"title": "Capítulo", "content": "c" * 5000} for _ in range(20)],
        "conclusion": "f" * 5000,
    }

    excerpt = build_review_excerpt(writer)

    assert len(excerpt) < 14000
    assert '"chapter_count": 20' in excerpt
    assert '"title": "Capítulo"' in excerpt
