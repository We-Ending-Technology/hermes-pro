from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4
from .jobs import job_service
from ..product_factory import PIPELINE_STAGES

@dataclass
class Product:
    topic: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str | None = None
    status: str = "queued"
    current_stage: str = PIPELINE_STAGES[0]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    job_id: str | None = None

class ProductService:
    def __init__(self) -> None:
        self.products: dict[str, Product] = {}
        self.idempotency: dict[str, str] = {}

    def create(self, topic: str, metadata: dict[str, Any] | None = None, idempotency_key: str | None = None) -> Product:
        if idempotency_key and idempotency_key in self.idempotency:
            return self.products[self.idempotency[idempotency_key]]
        product = Product(topic=topic.strip(), metadata=metadata or {})
        job = job_service.create("product_generation", {"product_id": product.id, "topic": product.topic}, idempotency_key)
        product.job_id = job.id
        self.products[product.id] = product
        if idempotency_key:
            self.idempotency[idempotency_key] = product.id
        return product

    def get(self, product_id: str) -> Product:
        if product_id not in self.products:
            raise KeyError(product_id)
        return self.products[product_id]

    def list(self) -> list[Product]:
        return list(self.products.values())

product_service = ProductService()
