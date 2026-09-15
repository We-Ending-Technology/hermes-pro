from __future__ import annotations

from dataclasses import dataclass

TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "cancelled", "blocked"},
    "running": {"qa", "retrying", "failed", "blocked", "cancelled"},
    "qa": {"approved", "retrying", "failed", "blocked"},
    "approved": {"published", "monitoring", "completed", "failed"},
    "published": {"monitoring", "completed", "failed"},
    "monitoring": {"completed", "retrying", "failed"},
    "retrying": {"pending", "running", "failed", "cancelled"},
    "failed": {"retrying", "cancelled"},
    "blocked": {"pending", "cancelled"},
    "cancelled": set(),
    "completed": set(),
}


@dataclass(frozen=True)
class Transition:
    allowed: bool
    reason: str


def transition_job(current: str, target: str) -> Transition:
    if target in TRANSITIONS.get(current, set()):
        return Transition(True, "allowed")
    return Transition(False, f"invalid transition: {current} -> {target}")


def retry_policy(attempt: int, max_attempts: int) -> tuple[bool, int]:
    if attempt >= max_attempts:
        return False, 0
    return True, min(3600, 2 ** max(0, attempt))


def calculate_operating_profit(revenue: float, costs: list[float]) -> float:
    return round(float(revenue) - sum(max(0.0, float(cost)) for cost in costs), 2)
