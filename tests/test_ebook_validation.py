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
async def test_short_ebook_gets_one_targeted_expansion_pass(monkeypatch):
    from worker import main

    short = {
        "introduction": "introducao curta",
        "chapters": [{"title": "Capitulo 1", "content": "texto curto"}],
        "conclusion": "conclusao curta",
    }
    expanded = _valid_content()
    gate_calls = []
    prompts = []

    def fake_validate(content):
        gate_calls.append(content)
        if len(gate_calls) == 1:
            return {
                "approved": False,
                "findings": ["Conteúdo insuficiente: 100 palavras; mínimo 1800."],
                "chapter_word_counts": [{"title": "Capitulo 1", "words": 10}],
            }
        return {"approved": True, "score": 100, "word_count": 2000, "findings": []}

    async def fake_complete_json_response(gateway, prompt, system, *, label, fallback=None):
        prompts.append((prompt, label))
        return ("revised-response", expanded)

    monkeypatch.setattr(main, "validate_ebook", fake_validate)
    monkeypatch.setattr(main, "complete_json_response", fake_complete_json_response)

    response, data, gate = await main.revise_ebook_if_needed(
        object(), "Agentes de IA na Prática", "original-response", short
    )

    assert response == "revised-response"
    assert data is expanded
    assert gate["approved"] is True
    assert len(prompts) == 1
    assert prompts[0][1] == "writer_revision"
    assert "2,200 words" in prompts[0][0]
    assert "Conteúdo insuficiente" in prompts[0][0]


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
