from backend.app.services.ebook_validation import validate_ebook
from backend.app.schemas_ext import is_kiwify_publishable_product

def _valid_content():
    paragraph = " ".join(["conteudo original pratico com exemplo e explicacao detalhada"] * 40)
    return {
        "introduction": paragraph,
        "chapters": [{"title": f"Capitulo {index}", "content": paragraph} for index in range(1, 6)],
        "conclusion": paragraph,
    }

def test_complete_ebook_passes_deterministic_gate():
    result = validate_ebook(_valid_content())
    assert result["approved"] is True
    assert result["word_count"] >= 1800
    assert result["chapter_count"] == 5

def test_short_ebook_is_rejected_even_if_ai_reviewer_would_approve():
    short = {"introduction": "texto curto", "chapters": [{"title": "Capitulo", "content": "poucas palavras"}], "conclusion": "fim"}
    result = validate_ebook(short)
    assert result["approved"] is False
    assert result["score"] < 80
    assert any("Conteúdo insuficiente" in finding for finding in result["findings"])

def test_checkout_requires_quality_gate_and_all_artifacts():
    product = {
        "status": "ready_to_publish",
        "metadata": {
            "artifact_status": "ready",
            "quality_score": 95,
            "quality_gate": {"approved": True},
            "artifacts": {"pdf": "https://storage/pdf", "docx": "https://storage/docx", "cover": "https://storage/cover"},
        },
    }
    assert is_kiwify_publishable_product(product) is True
    product["metadata"]["quality_gate"]["approved"] = False
    assert is_kiwify_publishable_product(product) is False
    product["metadata"]["quality_gate"]["approved"] = True
    del product["metadata"]["artifacts"]["cover"]
    assert is_kiwify_publishable_product(product) is False
    product["status"] = "completed"
    assert is_kiwify_publishable_product(product) is False


import pytest


@pytest.mark.asyncio
async def test_short_ebook_gets_targeted_section_additions_merged(monkeypatch):
    from worker import main

    original = {
        "introduction": "introducao original",
        "chapters": [
            {"title": "Capitulo 1", "content": "conteudo original"},
            {"title": "Capitulo 2", "content": "conteudo original 2"},
        ],
        "conclusion": "conclusao original",
    }
    additions = {
        "introduction_addition": "Contexto adicional prático.",
        "chapter_additions": [
            {"index": 1, "content": "Exemplo adicional para o capítulo dois."}
        ],
        "conclusion_addition": "Próximas ações e síntese final.",
    }
    gate_calls = []

    def fake_validate(content):
        gate_calls.append(content)
        if len(gate_calls) == 1:
            return {
                "approved": False,
                "score": 60,
                "findings": ["Conclusão curta."],
                "introduction_words": 100,
                "conclusion_words": 100,
                "chapter_word_counts": [
                    {"title": "Capitulo 1", "words": 250},
                    {"title": "Capitulo 2", "words": 120},
                ],
            }
        return {"approved": True, "score": 100, "word_count": 2000, "findings": []}

    captured = {}
    async def fake_complete_json_response(gateway, prompt, system, *, label, fallback=None):
        captured["prompt"] = prompt
        captured["label"] = label
        return ("revision-response", additions)

    monkeypatch.setattr(main, "validate_ebook", fake_validate)
    monkeypatch.setattr(main, "complete_json_response", fake_complete_json_response)

    response, revised, gate = await main.revise_ebook_if_needed(
        object(), "Agentes de IA", "original-response", original
    )

    assert response == "revision-response"
    assert gate["approved"] is True
    assert "Contexto adicional prático." in revised["introduction"]
    assert "Exemplo adicional para o capítulo dois." in revised["chapters"][1]["content"]
    assert revised["chapters"][0]["content"] == "conteudo original"
    assert "Próximas ações" in revised["conclusion"]
    assert captured["label"] == "writer_revision"
    assert "chapter_additions" in captured["prompt"]


@pytest.mark.asyncio
async def test_ebook_that_already_passes_skips_expansion(monkeypatch):
    from worker import main

    valid = _valid_content()
    monkeypatch.setattr(main, "validate_ebook", lambda _content: {"approved": True, "score": 100})
    async def unexpected(*args, **kwargs):
        pytest.fail("expansion must not run for a valid ebook")
    monkeypatch.setattr(main, "complete_json_response", unexpected)

    response, data, gate = await main.revise_ebook_if_needed(
        object(), "Tema", "writer-response", valid
    )
    assert response == "writer-response"
    assert data is valid
    assert gate["approved"] is True


@pytest.mark.asyncio
async def test_invalid_revision_keeps_original_manuscript(monkeypatch):
    from worker import main

    original = {
        "introduction": "texto original",
        "chapters": [{"title": "Capítulo", "content": "conteúdo original"}],
        "conclusion": "conclusão original",
    }
    calls = []
    def fake_validate(content):
        calls.append(content)
        return {"approved": False, "score": 50 if len(calls) == 1 else 40,
                "introduction_words": 0, "conclusion_words": 0,
                "chapter_word_counts": []}
    async def fake_complete_json_response(*args, **kwargs):
        return ("bad-revision", {"unexpected": "schema"})
    monkeypatch.setattr(main, "validate_ebook", fake_validate)
    monkeypatch.setattr(main, "complete_json_response", fake_complete_json_response)

    response, data, gate = await main.revise_ebook_if_needed(
        object(), "Tema", "original-response", original
    )
    assert response == "original-response"
    assert data == original
    assert gate["score"] == 50
