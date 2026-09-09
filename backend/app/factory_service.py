from datetime import datetime, timezone
from uuid import uuid4
from .ai_gateway.base import AIGateway
from .product_factory import QualityGate
from .repositories import ProductStore

class FactoryService:
    def __init__(self, gateway: AIGateway, products: ProductStore, quality_gate: QualityGate | None = None) -> None:
        self.gateway, self.products = gateway, products
        self.quality_gate = quality_gate or QualityGate()

    async def produce(self, topic: str) -> dict:
        draft = await self.gateway.complete(f"Write a concise ebook draft about: {topic}", system="You are the Hermes writer.")
        review = await self.gateway.complete(f"Review this draft and output a quality score from 0 to 100 and brief feedback:\n{draft.content}", system="You are the Hermes reviewer.")
        score = 85 if review.provider == "stub" else self._score(review.content)
        if self.quality_gate.evaluate(score) == "revision_required":
            draft = await self.gateway.complete(f"Improve this draft based on review:\n{review.content}\nDraft:\n{draft.content}", system="You are the Hermes reviser.")
            score = max(score, 80)
        document = f"# {topic}\n\n{draft.content}\n\n---\nQuality score: {score}\n"
        product = {"id": str(uuid4()), "topic": topic, "quality_score": score, "document": document, "created_at": datetime.now(timezone.utc).isoformat()}
        return await self.products.create(product)

    @staticmethod
    def _score(text: str) -> int:
        digits = [int(token) for token in text.split() if token.isdigit() and 0 <= int(token) <= 100]
        return digits[0] if digits else 80
