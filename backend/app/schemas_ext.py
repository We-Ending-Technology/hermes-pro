from typing import Any
from pydantic import BaseModel, Field

class ProductUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    metadata: dict[str, Any] | None = None


from pydantic import HttpUrl, field_validator


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
    """Fail closed: legacy status labels alone never authorize a checkout link."""
    metadata = product.get("metadata") or {}
    artifacts = metadata.get("artifacts") or {}
    quality_gate = metadata.get("quality_gate") or {}
    return (
        product.get("status") == "ready_to_publish"
        and metadata.get("artifact_status") == "ready"
        and all(
            isinstance(artifacts.get(kind), str) and artifacts.get(kind, "").startswith("https://")
            for kind in ("pdf", "docx", "cover")
        )
        and quality_gate.get("approved") is True
        and str(metadata.get("quality_score") or "").isdigit()
        and int(metadata.get("quality_score") or 0) >= 80
    )
