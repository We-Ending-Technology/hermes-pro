import pytest
from pydantic import ValidationError

from backend.app.schemas_ext import KiwifyPublicationRequest


def test_publication_requires_https_checkout_url():
    request = KiwifyPublicationRequest(
        product_id="kiwify-product-123",
        checkout_url="https://pay.kiwify.com.br/example",
    )
    assert request.product_id == "kiwify-product-123"
    assert str(request.checkout_url).startswith("https://")


def test_publication_rejects_non_https_checkout_url():
    with pytest.raises(ValidationError):
        KiwifyPublicationRequest(checkout_url="http://example.com/checkout")


def test_blank_kiwify_product_id_is_normalized_to_none():
    request = KiwifyPublicationRequest(
        product_id="   ",
        checkout_url="https://pay.kiwify.com.br/example",
    )
    assert request.product_id is None
