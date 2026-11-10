import pytest
from pydantic import ValidationError

from backend.app.schemas_ext import (
    KiwifyPublicationRequest,
    is_kiwify_publishable_product,
)


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


def publishable_product():
    return {
        "status": "ready_to_publish",
        "metadata": {
            "artifact_status": "ready",
            "quality_score": "85",
            "quality_gate": {"approved": True, "page_count": 10, "illustration_count": 4},
            "artifacts": {
                "pdf": "https://storage.example/product.pdf",
                "docx": "https://storage.example/product.docx",
                "cover": "https://storage.example/cover.png",
            },
        },
    }


def test_only_fully_validated_product_can_be_published():
    assert is_kiwify_publishable_product(publishable_product()) is True


@pytest.mark.parametrize("status", [
    "completed", "queued", "generating", "review_required", "failed", "cancelled", None
])
def test_legacy_or_unfinished_status_cannot_be_published(status):
    product = publishable_product()
    product["status"] = status
    assert is_kiwify_publishable_product(product) is False


@pytest.mark.parametrize("metadata_change", [
    {"quality_gate": {"approved": False}},
    {"quality_gate": {"approved": True, "page_count": 9, "illustration_count": 4}},
    {"quality_gate": {"approved": True, "page_count": 10, "illustration_count": 3}},
    {"quality_score": "79"},
    {"artifact_status": "not_verified"},
    {"artifacts": {"pdf": "http://storage.example/product.pdf"}},
    {"artifacts": {"pdf": "https://storage.example/product.pdf", "docx": "https://storage.example/product.docx"}},
])
def test_missing_or_invalid_quality_evidence_blocks_publication(metadata_change):
    product = publishable_product()
    product["metadata"].update(metadata_change)
    assert is_kiwify_publishable_product(product) is False
