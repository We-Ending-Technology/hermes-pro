from dataclasses import dataclass
from typing import Any

PIPELINE_STAGES = ("topic", "job", "writer", "reviewer", "cover", "document", "validation", "publication", "sales")

@dataclass(frozen=True)
class QualityGate:
    minimum_score: int = 80

    def evaluate(self, quality_score: int) -> str:
        return "approved" if quality_score >= self.minimum_score else "revision_required"

class ProductFactory:
    def __init__(self, quality_gate: QualityGate | None = None) -> None:
        self.quality_gate = quality_gate or QualityGate()

    def plan(self, topic: str) -> dict[str, Any]:
        return {"topic": topic, "stages": list(PIPELINE_STAGES), "status": "planned"}

    def validate(self, quality_score: int) -> dict[str, Any]:
        return {"quality_score": quality_score, "decision": self.quality_gate.evaluate(quality_score)}
