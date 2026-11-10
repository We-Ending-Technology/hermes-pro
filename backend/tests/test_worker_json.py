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

    assert len(excerpt) < 11000
    assert '"chapter_count": 20' in excerpt
    assert '"title": "Capítulo"' in excerpt


def test_parse_json_object_never_salvages_nested_chapter_from_malformed_manuscript():
    malformed = (
        '{"introduction":"texto", "chapters":[{"title":"Capítulo 1",'
        '"content":"texto válido"}], "conclusion": }'
    )

    with pytest.raises(ValueError, match="malformed JSON object"):
        parse_json_object(malformed)


def test_is_ebook_payload_rejects_valid_json_wrapper_without_manuscript_sections():
    from worker.json_utils import is_ebook_payload

    assert is_ebook_payload({
        "introduction": "Introdução",
        "chapters": [{"title": "Capítulo 1", "content": "Conteúdo"}],
        "conclusion": "Conclusão",
    })
    assert not is_ebook_payload({"title": "Ebook", "content": "Apenas um trecho"})


@pytest.mark.asyncio
async def test_complete_json_response_repairs_valid_json_with_wrong_ebook_schema():
    from types import SimpleNamespace
    from worker.main import complete_json_response
    from worker.json_utils import is_ebook_payload

    class FakeGateway:
        def __init__(self):
            self.calls = 0

        async def complete(self, prompt, system=None):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(content='{"title":"Ebook","content":"apenas um trecho"}')
            return SimpleNamespace(content='{"introduction":"Introdução","chapters":[{"title":"Capítulo 1","content":"Conteúdo"}],"conclusion":"Conclusão"}')

    gateway = FakeGateway()
    _, manuscript = await complete_json_response(
        gateway,
        "Write a complete ebook with introduction, chapters and conclusion.",
        "Return only JSON.",
        label="writer",
        validator=is_ebook_payload,
    )

    assert gateway.calls == 2
    assert is_ebook_payload(manuscript)
