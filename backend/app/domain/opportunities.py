from __future__ import annotations

from typing import Any

POSITIVE = ("demand", "margin", "ease", "conversion_probability", "capacity")
NEGATIVE = ("competition", "cost", "risk")


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, number))


def score_opportunity(signals: dict[str, Any]) -> dict[str, Any]:
    dimensions: dict[str, float] = {}
    for name in POSITIVE + NEGATIVE:
        value = _number(signals.get(name))
        if value is not None:
            dimensions[name] = value

    if not dimensions:
        return {"score": 0.0, "confidence": 0.0, "dimensions": {}, "findings": ["no_signals"]}

    positive_values = [dimensions[name] for name in POSITIVE if name in dimensions]
    negative_values = [dimensions[name] for name in NEGATIVE if name in dimensions]
    positive = sum(positive_values) / len(positive_values) if positive_values else 0.0
    negative = sum(negative_values) / len(negative_values) if negative_values else 0.0
    score = round(max(0.0, min(100.0, positive - (negative * 0.25))), 2)
    confidence = round(len(dimensions) / len(POSITIVE + NEGATIVE), 2)
    findings = []
    if len(dimensions) < len(POSITIVE + NEGATIVE):
        findings.append("incomplete_signals")
    if negative >= 50:
        findings.append("high_commercial_risk")
    return {"score": score, "confidence": confidence, "dimensions": dimensions, "findings": findings}
