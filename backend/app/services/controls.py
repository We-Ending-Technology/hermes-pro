from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ControlDecision:
    allowed: bool
    reason: str


DEFAULT_POLICIES = {
    "observe": {"mode": "observe", "requires_approval": False},
    "retry_job": {"mode": "reversible", "requires_approval": False},
    "provider_failover": {"mode": "reversible", "requires_approval": False},
    "produce": {"mode": "financially_bounded", "requires_approval": False},
    "publish": {"mode": "human_approval", "requires_approval": True},
    "refund": {"mode": "human_approval", "requires_approval": True},
    "credential_change": {"mode": "human_approval", "requires_approval": True},
}


class ControlService:
    def __init__(self, settings: Mapping[str, object] | None = None) -> None:
        self._settings = dict(settings or {})
        self._switches: dict[str, bool] = {}
        self._policies = {**DEFAULT_POLICIES, **dict(self._settings.get("autonomy_policies") or {})}

    def set_kill_switch(self, name: str, enabled: bool) -> None:
        self._switches[name] = enabled

    def get_status(self) -> dict[str, object]:
        return {"kill_switches": dict(self._switches), "settings": dict(self._settings), "policies": self._policies}

    def is_allowed(self, action: str, estimated_cost: float = 0.0) -> ControlDecision:
        if self._switches.get("global", False):
            return ControlDecision(False, "global kill switch enabled")
        if self._switches.get(action, False):
            return ControlDecision(False, f"kill switch enabled: {action}")
        policy = self._policies.get(action)
        if not policy:
            return ControlDecision(False, f"unknown autonomous action: {action}")
        if policy.get("requires_approval"):
            return ControlDecision(False, f"human approval required: {action}")
        max_cost = float(policy.get("max_cost", 0) or 0)
        if max_cost > 0 and estimated_cost > max_cost:
            return ControlDecision(False, f"action cost exceeds policy limit: {action}")
        budget = float(self._settings.get("daily_budget", 0.0) or 0.0)
        spent = float(self._settings.get("daily_spend", 0.0) or 0.0)
        if budget > 0 and spent + max(0.0, estimated_cost) > budget:
            return ControlDecision(False, "daily budget exceeded")
        return ControlDecision(True, "allowed")