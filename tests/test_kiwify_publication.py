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
            "quality_gate": {"approved": True, "page_count": 10, "illustration_count": 4, "ai_cover_generated": True},
            "cover_art": {"provider": "ovhcloud", "model": "stable-diffusion-xl-base-v10", "generated": True},
            "marketing_pack_status": "ready",
            "marketing_pack": {
                "product_description": "Descrição comercial honesta do ebook. " * 12,
                "short_description": "Guia prático e objetivo para aplicar os conceitos do livro com orientações claras, exemplos e atividades úteis.",
                "target_audience": "Pessoas que querem aprender e aplicar os conceitos do guia.",
                "contents": ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5", "Item 6"],
                "benefits": ["Benefício 1", "Benefício 2", "Benefício 3", "Benefício 4"],
                "faq": [{"question": "O que inclui?", "answer": "O conteúdo completo do guia."}] * 3,
                "keywords": ["ebook", "guia", "prático", "digital", "aprendizado"],
                "social_posts": [
                    {"platform": "Instagram", "hook": "Veja o guia", "caption": "Conteúdo do ebook", "cta": "Saiba mais"},
                    {"platform": "TikTok", "hook": "Aprenda", "caption": "Conteúdo do ebook", "cta": "Confira"},
                    {"platform": "Facebook", "hook": "Guia prático", "caption": "Conteúdo do ebook", "cta": "Conheça"},
                ],
            },
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



@pytest.mark.parametrize("cover_art_change", [
    {"provider": "local_vector", "generated": True},
    {"provider": "ai_horde", "generated": False},
    {"provider": "ai_horde", "model": "SDXL 1.0", "generated": True},
])
def test_publication_requires_verified_ai_generated_cover(cover_art_change):
    product = publishable_product()
    product["metadata"]["cover_art"] = cover_art_change
    if cover_art_change.get("provider") in {"ai_horde", "ovhcloud"} and cover_art_change.get("generated") is True:
        assert is_kiwify_publishable_product(product) is True
    else:
        assert is_kiwify_publishable_product(product) is False



def test_publication_requires_validated_marketing_pack():
    product = publishable_product()
    product["metadata"]["marketing_pack"] = {}
    product["metadata"]["marketing_pack_status"] = "missing"
    assert is_kiwify_publishable_product(product) is False
