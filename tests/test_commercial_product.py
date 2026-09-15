from backend.app.commercial import build_commercial_metadata


def test_commercial_metadata_has_sellable_fields_and_price_basis():
    result = build_commercial_metadata(
        strategy={
            "title": "IA para Renda Extra",
            "subtitle": "Guia prático para começar",
            "audience": "iniciantes",
            "category": "negócios",
            "outline": ["Começo", "Execução"],
        },
        description="Um guia prático.",
        short_description="Guia prático de IA.",
        keywords=["IA", "renda extra"],
        suggested_price=29.90,
        price_rationale="Preço recomendado como posicionamento de entrada; validar contra comparáveis reais.",
    )

    assert result["title"] == "IA para Renda Extra"
    assert result["subtitle"] == "Guia prático para começar"
    assert result["description"] == "Um guia prático."
    assert result["short_description"] == "Guia prático de IA."
    assert result["audience"] == "iniciantes"
    assert result["category"] == "negócios"
    assert result["keywords"] == ["IA", "renda extra"]
    assert result["suggested_price"] == 29.90
    assert result["price_rationale"]
    assert result["price_basis"] == "recommendation"
