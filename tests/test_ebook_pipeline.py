import json

from backend.app.services.artifacts import (
    build_docx_artifact,
    build_pdf_artifact,
    prepare_artifact_context,
    validate_artifacts,
)
from backend.app.services.ebook_validation import validate_ebook


def _valid_content():
    paragraph = " ".join(["conteudo tecnico aplicavel"] * 150)
    return {
        "introduction": paragraph,
        "chapters": [
            {"title": f"Capitulo {index}", "content": paragraph}
            for index in range(1, 9)
        ],
        "conclusion": paragraph,
        "illustrations": [
            {
                "title": f"Ilustracao {index}",
                "description": "Fluxo prático específico do capítulo e seus critérios.",
                "caption": "Aplicação prática do método.",
                "alt_text": "Diagrama ilustrativo do procedimento.",
                "steps": ["Planejar", "Executar", "Validar"],
            }
            for index in range(1, 5)
        ],
    }


def test_ebook_artifact_pipeline_builds_and_validates_pdf_docx_and_cover():
    data = _valid_content()
    content_gate = validate_ebook(data)
    assert content_gate["approved"] is True

    context = prepare_artifact_context(
        "Ebook de teste Hermes",
        "Material técnico de validação",
        json.dumps(data, ensure_ascii=False),
        cover_artwork=None,
    )
    pdf = build_pdf_artifact("Ebook de teste Hermes", "Material técnico de validação", context)
    docx = build_docx_artifact("Ebook de teste Hermes", "Material técnico de validação", context)
    artifacts = {
        "cover": ("ebook/cover.png", context["cover"], "image/png"),
        "pdf": pdf,
        "docx": docx,
    }

    gate = validate_artifacts(artifacts)
    assert gate["approved"] is True
    assert gate["page_count"] >= 10
    assert gate["illustration_count"] >= 4
    assert artifacts["cover"][1].startswith(bytes.fromhex("89504e470d0a1a0a"))
    assert artifacts["pdf"][1].startswith(b"%PDF-")
    assert artifacts["docx"][1].startswith(bytes.fromhex("504b0304"))
