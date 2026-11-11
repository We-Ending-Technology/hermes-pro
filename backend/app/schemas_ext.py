from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ProductUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    metadata: dict[str, Any] | None = None


class KiwifyPublicationRequest(BaseModel):
    product_id: str | None = Field(default=None, max_length=160)
    checkout_url: HttpUrl

    @field_validator("checkout_url")
    @classmethod
    def require_https_checkout(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Kiwify checkout URL must use HTTPS")
        return value

    @field_validator("product_id")
    @classmethod
    def normalize_product_id(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else None
        return cleaned or None


def is_kiwify_publishable_product(product: dict) -> bool:
    """Fail closed: a checkout link is allowed only for a fully validated commercial ebook."""
    metadata = product.get("metadata") or {}
    artifacts = metadata.get("artifacts") or {}
    quality_gate = metadata.get("quality_gate") or {}
    cover_art = metadata.get("cover_art") or {}
    marketing_pack = metadata.get("marketing_pack") or {}
    try:
        page_count = int(quality_gate.get("page_count") or 0)
        illustration_count = int(quality_gate.get("illustration_count") or 0)
        quality_score = int(metadata.get("quality_score") or 0)
    except (TypeError, ValueError):
        return False
    return (
        product.get("status") == "ready_to_publish"
        and metadata.get("artifact_status") == "ready"
        and all(
            isinstance(artifacts.get(kind), str) and artifacts.get(kind, "").startswith("https://")
            for kind in ("pdf", "docx", "cover")
        )
        and quality_gate.get("approved") is True
        and quality_gate.get("ai_cover_generated") is True
        and cover_art.get("generated") is True
        and cover_art.get("provider") == "ai_horde"
        and metadata.get("marketing_pack_status") == "ready"
        and isinstance(marketing_pack.get("product_description"), str)
        and len(marketing_pack.get("product_description", "").strip()) >= 300
        and isinstance(marketing_pack.get("short_description"), str)
        and len(marketing_pack.get("short_description", "").strip()) >= 80
        and isinstance(marketing_pack.get("benefits"), list)
        and len(marketing_pack.get("benefits")) >= 4
        and isinstance(marketing_pack.get("faq"), list)
        and len(marketing_pack.get("faq")) >= 3
        and isinstance(marketing_pack.get("keywords"), list)
        and len(marketing_pack.get("keywords")) >= 5
        and isinstance(marketing_pack.get("social_posts"), list)
        and len(marketing_pack.get("social_posts")) >= 3
        and page_count >= 10
        and illustration_count >= 4
        and quality_score >= 80
    )
