from backend.app.commercial import parse_chat_command


def test_chat_create_ebook_is_an_action():
    action = parse_chat_command("Crie um ebook sobre organização financeira para iniciantes")
    assert action == {
        "action": "create_product",
        "topic": "organização financeira para iniciantes",
    }


def test_chat_price_update_is_an_action():
    action = parse_chat_command("Mude o preço do ebook para R$ 29,90")
    assert action == {"action": "set_price", "price": 29.90}
