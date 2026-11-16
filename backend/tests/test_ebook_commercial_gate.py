from backend.app.services.ebook_validation import MIN_ILLUSTRATIONS, MIN_PAGES, MIN_TOTAL_WORDS, validate_ebook


def test_commercial_ebook_gate_requires_forty_pages_and_eight_illustrations():
    assert MIN_PAGES == 40
    assert MIN_ILLUSTRATIONS == 8
    assert MIN_TOTAL_WORDS >= 12000


def test_four_illustrations_are_not_approved_for_commercial_ebook():
    illustrations = [
        {
            "title": f"Ilustração {index}",
            "description": "Diagrama específico do capítulo e do assunto.",
            "caption": "Aplicação prática do conceito.",
            "alt_text": "Infográfico com etapas do processo.",
            "steps": ["Analisar", "Planejar", "Executar"],
        }
        for index in range(4)
    ]
    result = validate_ebook({
        "introduction": "Introdução breve.",
        "chapters": [{"title": "Capítulo", "content": "Conteúdo breve."}],
        "conclusion": "Conclusão breve.",
        "illustrations": illustrations,
    })
    assert result["approved"] is False
    assert any("Ilustrações insuficientes" in finding for finding in result["findings"])
