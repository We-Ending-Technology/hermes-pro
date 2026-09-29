from typing import Any
from pydantic import BaseModel, Field

class ProductUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    metadata: dict[str, Any] | None = None
