from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class OpportunityInput:
    demand: float | None = None
    margin: float | None = None
    ease: float | None = None
    conversion: float | None = None
    competition: float | None = None
    cost: float | None = None
    risk: float | None = None


@dataclass(frozen=True)
class OpportunityScore:
    score: float
    confidence: float
    dimensions: Mapping[str, float | None]
    findings: tuple[str, ...]
    action: str


class OpportunityEngine:
    _weights = {"demand": .22, "margin": .20, "ease": .14, "conversion": .18, "competition": -.10, "cost": -.08, "risk": -.08}

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    def score(self, opportunity: OpportunityInput) -> OpportunityScore:
        dimensions = {name: None if value is None else self._clamp(value) for name, value in opportunity.__dict__.items()}
        available = [value for value in dimensions.values() if value is not None]
        confidence = round(len(available) / len(dimensions) * 100, 2)
        if not available:
            return OpportunityScore(0.0, 0.0, dimensions, ("insufficient evidence",), "research")
        raw = 50.0
        for name, weight in self._weights.items():
            value = dimensions[name]
            if value is not None:
                signed = value if weight > 0 else 100.0 - value
                raw += (signed - 50.0) * abs(weight)
        score = round(self._clamp(raw), 2)
        findings: list[str] = []
        if confidence < 60:
            action = "research"
            findings.append("confidence reduced because material signals are missing")
        elif score >= 70:
            action = "prioritize"
        elif score >= 50:
            action = "validate"
        else:
            action = "deprioritize"
        return OpportunityScore(score, confidence, dimensions, tuple(findings), action)

    def decide(self, score: OpportunityScore, policy: Mapping[str, float] | None = None) -> str:
        policy = policy or {}
        if score.confidence < float(policy.get("minimum_confidence", 60)):
            return "research"
        return "produce" if score.score >= float(policy.get("minimum_score", 70)) else "validate"
