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
