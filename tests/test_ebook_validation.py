import pytest
from pydantic import ValidationError

from backend.app.schemas_ext import (
    KiwifyPublicationRequest,
    is_kiwify_publishable_product,
)
from backend.app.services.artifacts import build_artifacts, validate_artifacts
from backend.app.services.ebook_validation import validate_ebook


def _valid_content():
    paragraph = " ".join(["conteudo original pratico com exemplo e explicacao detalhada"] * 60)
    illustrations = [
        {
            "title": f"Fluxo visual {index}",
            "description": f"Diagrama específico do tema que explica a etapa {index} e sua aplicação prática.",
            "caption": f"Etapa {index}: aplicação prática.",
            "alt_text": f"Infográfico com quatro etapas do processo {index}.",
            "chapter_index": index - 1,
            "steps": [
                "Identifique o objetivo e o contexto",
                "Organize os recursos e as prioridades",
                "Execute a atividade com método",
                "Revise os resultados e faça ajustes",
            ],
        }
        for index in range(1, 5)
    ]
    return {
        "introduction": paragraph,
        "chapters": [
            {"title": f"Capítulo {index}", "content": paragraph}
            for index in range(1, 9)
        ],
        "conclusion": paragraph,
        "illustrations": illustrations,
    }


def test_complete_ebook_passes_commercial_content_gate():
    result = validate_ebook(_valid_content())
    assert result["approved"] is True
    assert result["word_count"] >= 3500
    assert result["chapter_count"] >= 8
    assert result["illustration_count"] == 4
    assert result["required_standard"]["minimum_pages"] == 10


def test_short_ebook_is_rejected_even_if_ai_reviewer_would_approve():
    short = {
        "introduction": "texto curto",
        "chapters": [{"title": "Capítulo", "content": "poucas palavras"}],
        "conclusion": "fim",
        "illustrations": [],
    }
    result = validate_ebook(short)
    assert result["approved"] is False
    assert result["score"] < 80
    assert any("Conteúdo insuficiente" in finding for finding in result["findings"])
    assert any("Ilustrações insuficientes" in finding for finding in result["findings"])


def test_missing_internal_illustrations_block_approval():
    content = _valid_content()
    content["illustrations"] = content["illustrations"][:2]
    result = validate_ebook(content)
    assert result["approved"] is False
    assert result["illustration_count"] == 2
    assert any("Ilustrações insuficientes" in finding for finding in result["findings"])


def test_artifact_pipeline_embeds_four_illustrations_and_reaches_ten_pages():
    content = _valid_content()
    artifacts = build_artifacts("Guia de Teste", "Manual ilustrado", __import__("json").dumps(content, ensure_ascii=False))
    gate = validate_artifacts(artifacts)
    assert gate["approved"] is True, gate["findings"]
    assert gate["page_count"] >= 10
    assert gate["illustration_count"] >= 4
    assert gate["pdf_image_count"] >= 5
    assert gate["docx_image_count"] >= 5


def test_publication_requires_content_and_artifact_quality_gate():
    product = {
        "status": "ready_to_publish",
        "metadata": {
            "artifact_status": "ready",
            "quality_score": 95,
            "quality_gate": {"approved": True, "page_count": 10, "illustration_count": 4, "ai_cover_generated": True},
            "cover_art": {"provider": "ai_horde", "model": "SDXL 1.0", "generated": True},
            "marketing_pack_status": "ready",
            "marketing_pack": {
                "product_description": "Descrição comercial honesta do ebook. " * 12,
                "short_description": "Guia prático e objetivo para aplicar os conceitos do livro.",
                "benefits": ["Benefício 1", "Benefício 2", "Benefício 3", "Benefício 4"],
                "faq": [{"question": "O que inclui?", "answer": "O conteúdo completo do guia."}] * 3,
                "keywords": ["ebook", "guia", "prático", "digital", "aprendizado"],
                "social_posts": [
                    {"platform": "Instagram", "hook": "Veja o guia", "caption": "Conteúdo do ebook", "cta": "Saiba mais"},
                    {"platform": "TikTok", "hook": "Aprenda", "caption": "Conteúdo do ebook", "cta": "Confira"},
                    {"platform": "Facebook", "hook": "Guia prático", "caption": "Conteúdo do ebook", "cta": "Conheça"},
                ],
            },
            "artifacts": {
                "pdf": "https://storage/pdf",
                "docx": "https://storage/docx",
                "cover": "https://storage/cover",
            },
        },
    }
    assert is_kiwify_publishable_product(product) is True
    product["metadata"]["quality_gate"]["page_count"] = 9
    assert is_kiwify_publishable_product(product) is False
    product["metadata"]["quality_gate"]["page_count"] = 10
    product["metadata"]["quality_gate"]["illustration_count"] = 3
    assert is_kiwify_publishable_product(product) is False
    product["metadata"]["quality_gate"]["illustration_count"] = 4
    product["metadata"]["quality_gate"]["approved"] = False
    assert is_kiwify_publishable_product(product) is False
    product["metadata"]["quality_gate"]["approved"] = True
    del product["metadata"]["artifacts"]["cover"]
    assert is_kiwify_publishable_product(product) is False
    product["status"] = "completed"
    assert is_kiwify_publishable_product(product) is False


def test_publication_request_requires_https_checkout_url():
    request = KiwifyPublicationRequest(
        product_id="kiwify-product-123",
        checkout_url="https://pay.kiwify.com.br/example",
    )
    assert request.product_id == "kiwify-product-123"
    assert str(request.checkout_url).startswith("https://")
    with pytest.raises(ValidationError):
        KiwifyPublicationRequest(checkout_url="http://example.com/checkout")


def test_blank_kiwify_product_id_is_normalized_to_none():
    request = KiwifyPublicationRequest(
        product_id="   ",
        checkout_url="https://pay.kiwify.com.br/example",
    )
    assert request.product_id is None


@pytest.mark.asyncio
async def test_short_ebook_expansion_adds_missing_chapters_and_illustrations(monkeypatch):
    from worker import main

    original = {
        "introduction": "introdução original",
        "chapters": [
            {"title": "Capítulo 1", "content": "conteúdo original"},
            {"title": "Capítulo 2", "content": "conteúdo original 2"},
        ],
        "conclusion": "conclusão original",
        "illustrations": [],
    }
    new_chapters = [
        {"title": f"Novo capítulo {index}", "content": f"Conteúdo prático e original do capítulo {index}."}
        for index in range(1, 7)
    ]
    additions_round_1 = {
        "introduction_addition": "Contexto adicional prático.",
        "chapter_additions": [{"index": 1, "content": "Exemplo adicional para o capítulo dois."}],
        "new_chapters": new_chapters,
        "conclusion_addition": "Próximas ações e síntese final.",
        "illustrations": _valid_content()["illustrations"],
    }
    additions_round_2 = {
        "chapter_additions": [
            {"index": index, "content": "segunda rodada com análise, exemplo prático, critérios de decisão e passos adicionais para completar o capítulo com profundidade suficiente."}
            for index in (1, 3, 4, 5, 6, 7)
        ],
        "new_chapters": [],
        "illustrations": [],
    }
    gate_calls = []

    def fake_validate(content):
        gate_calls.append(content)
        if len(gate_calls) == 1:
            return {
                "approved": False,
                "score": 60,
                "word_count": 700,
                "chapter_count": 2,
                "illustration_count": 0,
                "findings": ["Conteúdo insuficiente."],
                "introduction_words": 100,
                "conclusion_words": 100,
                "chapter_word_counts": [
                    {"title": "Capítulo 1", "words": 250},
                    {"title": "Capítulo 2", "words": 120},
                ],
            }
        if len(gate_calls) == 2:
            return {
                "approved": False,
                "score": 79,
                "word_count": 3200,
                "chapter_count": 8,
                "illustration_count": 4,
                "findings": ["Conteúdo insuficiente.", "Capítulos curtos."],
                "introduction_words": 240,
                "conclusion_words": 220,
                "chapter_word_counts": [
                    {"title": f"Capítulo {index}", "words": 400 if index in (1, 3) else 250}
                    for index in range(1, 9)
                ],
            }
        return {
            "approved": True,
            "score": 100,
            "word_count": 4200,
            "chapter_count": 8,
            "illustration_count": 4,
            "findings": [],
        }

    captured = {"prompts": [], "labels": []}
    async def fake_complete_json_response(gateway, prompt, system, *, label, fallback=None):
        captured["prompts"].append(prompt)
        captured["labels"].append(label)
        if len(captured["prompts"]) == 1:
            return ("revision-response-1", additions_round_1)
        return ("revision-response-2", additions_round_2)

    monkeypatch.setattr(main, "validate_ebook", fake_validate)
    monkeypatch.setattr(main, "complete_json_response", fake_complete_json_response)

    response, revised, gate = await main.revise_ebook_if_needed(
        object(), "Agentes de IA", "original-response", original
    )

    assert response == "revision-response-2"
    assert gate["approved"] is True
    assert "Contexto adicional prático." in revised["introduction"]
    assert "Exemplo adicional para o capítulo dois." in revised["chapters"][1]["content"]
    assert len(revised["chapters"]) == 8
    assert len(revised["illustrations"]) == 4
    assert "Próximas ações" in revised["conclusion"]
    assert "segunda rodada" in revised["chapters"][7]["content"]
    assert captured["labels"] == ["writer_revision_round_1", "writer_revision_round_2"]
    assert "new_chapters" in captured["prompts"][0]
    assert "minimum_addition_words" in captured["prompts"][1]

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
        return {
            "approved": False,
            "score": 50 if len(calls) == 1 else 40,
            "word_count": 20,
            "chapter_count": 1,
            "illustration_count": 0,
            "introduction_words": 0,
            "conclusion_words": 0,
            "chapter_word_counts": [],
            "findings": ["insuficiente"],
        }

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


def test_product_metadata_merge_preserves_rebuild_history_and_previous_artifacts():
    from worker.main import build_product_metadata

    previous_artifacts = {"pdf": "https://storage/old.pdf", "docx": "https://storage/old.docx"}
    publications = {"kiwify": {"status": "relink_required", "verified": False}}
    existing = {
        "rebuild_attempts": 1,
        "rebuild_requested_at": "2026-11-10T20:24:00Z",
        "previous_artifacts": previous_artifacts,
        "publications": publications,
    }
    result = build_product_metadata(
        existing,
        strategy_data={"title": "Novo título"},
        content="conteúdo novo",
        content_data={"chapters": []},
        review_data={"approved": False, "score": 92},
        quality_score=79,
        content_gate={"approved": False, "word_count": 3449, "findings": ["curto"]},
        ai_review_approved=True,
        approved=False,
        ai_provider="gemini",
        ai_model="gemini-flash",
    )
    assert result["rebuild_attempts"] == 1
    assert result["previous_artifacts"] == previous_artifacts
    assert result["publications"] == publications
    assert result["artifact_status"] == "revision_required"
    assert result["quality_gate"]["approved"] is False


def test_metric_only_ai_review_rejection_is_overridden_when_content_gate_passes():
    from worker.main import normalize_review_result

    review = {
        "approved": False,
        "score": 75,
        "findings": [
            "O conteúdo é excelente e bem estruturado.",
            "A profundidade e a precisão factual atendem perfeitamente ao nicho.",
            "Contudo, o portfólio de ilustrações possui apenas 3 briefs, abaixo do mínimo de 4.",
            "A contagem de palavras e a extensão em páginas carecem de verificação para atingir os mínimos.",
        ],
    }
    gate = {"approved": True, "score": 100, "findings": []}
    normalized = normalize_review_result(review, gate)
    assert normalized["approved"] is True
    assert normalized["score"] == 90
    assert len(normalized["ignored_metric_findings"]) == 2
    assert len(normalized["positive_findings"]) == 2
    assert normalized["findings"] == []


def test_substantive_ai_review_rejection_is_not_overridden_by_metrics_gate():
    from worker.main import normalize_review_result

    review = {
        "approved": False,
        "score": 65,
        "findings": ["O conteúdo é superficial e repetitivo, com exemplos insuficientes."],
    }
    gate = {"approved": True, "score": 100, "findings": []}
    normalized = normalize_review_result(review, gate)
    assert normalized["approved"] is False
    assert normalized["score"] == 65


def test_quality_service_uses_current_validator_minimum_keys():
    from backend.app.services.quality import QualityService

    report = QualityService().evaluate({
        "title": "Guia completo de teste",
        "audience": "Leitores que precisam de um guia prático",
        "content_data": _valid_content(),
    })

    assert report.decision == "approved"
    assert report.score >= 80
    assert report.dimensions["content_length"] == 100
    assert report.dimensions["chapter_structure"] == 100
    assert report.dimensions["chapter_depth"] == 100
