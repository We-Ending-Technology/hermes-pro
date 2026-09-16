from backend.app.services.document_assets import build_cover, build_docx, build_pdf, normalize_content


def test_normalize_content_keeps_editable_structure():
    content = normalize_content('{"introduction":"Intro","chapters":[{"title":"Um","content":"Texto"}],"conclusion":"Fim"}')
    assert content["chapters"][0]["title"] == "Um"
    assert content["chapters"][0]["content"] == "Texto"


def test_document_and_cover_builders_return_real_bytes():
    content = normalize_content({"introduction": "Intro", "chapters": [{"title": "Um", "content": "Texto"}], "conclusion": "Fim"})
    assert build_docx("Teste", content).startswith(b"PK")
    assert build_pdf("Teste", content).startswith(b"%PDF")
    assert build_cover("Teste", "Subtitulo").startswith(b"\x89PNG")
