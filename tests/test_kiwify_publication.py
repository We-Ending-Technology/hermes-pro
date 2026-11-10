import pytest
from pydantic import ValidationError

from backend.app.schemas_ext import KiwifyPublicationRequest, is_kiwify_publishable_status


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



def test_worker_ready_to_publish_status_can_be_linked_to_kiwify():
    assert is_kiwify_publishable_status("ready_to_publish") is True


def test_legacy_completed_products_remain_publishable():
    assert is_kiwify_publishable_status("completed") is True


@pytest.mark.parametrize("status", ["queued", "generating", "review_required", "cancelled", None])
def test_unfinished_products_cannot_be_linked_to_kiwify(status):
    assert is_kiwify_publishable_status(status) is False
