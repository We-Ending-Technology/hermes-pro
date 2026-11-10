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