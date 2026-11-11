from backend.app.services.kiwify_api import safe_product, safe_sale


def test_safe_product_keeps_catalog_fields_only():
    result = safe_product({
        "id": "p-1",
        "name": "Ebook",
        "status": "active",
        "secret": "must-not-leak",
    })
    assert result == {"id": "p-1", "name": "Ebook", "status": "active"}
    assert "secret" not in result


def test_safe_sale_never_exposes_buyer_personal_data():
    result = safe_sale({
        "id": "s-1",
        "reference": "R-1",
        "status": "paid",
        "net_amount": 17.5,
        "currency": "BRL",
        "product": {"id": "p-1", "name": "Ebook"},
        "customer": {"name": "Buyer", "email": "buyer@example.com", "cpf": "123"},
    })
    assert result["id"] == "s-1"
    assert result["product"]["name"] == "Ebook"
    assert "customer" not in result
    assert "email" not in result


def test_safe_sale_handles_missing_product():
    result = safe_sale({"id": "s-2", "status": "pending"})
    assert result["product"] == {"id": None, "name": None}
