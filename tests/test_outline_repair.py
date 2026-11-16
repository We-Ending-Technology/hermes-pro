from worker.main import normalize_outline_titles


def test_outline_repair_completes_short_outline_to_ten_chapters():
    strategy = {
        "outline": [
            "1. Conceitos básicos",
            "2. Planejamento",
            "3. Ferramentas",
            "4. Implementação",
            "5. Exemplos",
            "6. Acompanhamento",
        ]
    }

    titles = normalize_outline_titles(strategy, "Automação de pequenos negócios")

    assert len(titles) == 10
    assert titles[:6] == [
        "Conceitos básicos",
        "Planejamento",
        "Ferramentas",
        "Implementação",
        "Exemplos",
        "Acompanhamento",
    ]
    assert strategy["outline"] == titles


def test_outline_repair_accepts_chapter_objects_and_removes_duplicates():
    strategy = {
        "outline": [
            {"title": "Capítulo 1: Introdução"},
            {"chapter_title": "Capítulo 2: Fundamentos"},
            {"name": "Capítulo 1: Introdução"},
        ]
    }

    titles = normalize_outline_titles(strategy, "Gestão de estoque")

    assert len(titles) == 10
    assert titles[0] == "Introdução"
    assert titles[1] == "Fundamentos"
    assert len({title.casefold() for title in titles}) == 10


def test_outline_repair_accepts_newline_delimited_outline():
    strategy = {"outline": "1. Primeiro\n2. Segundo\n3. Terceiro"}

    titles = normalize_outline_titles(strategy, "Finanças pessoais")

    assert len(titles) == 10
    assert titles[:3] == ["Primeiro", "Segundo", "Terceiro"]
