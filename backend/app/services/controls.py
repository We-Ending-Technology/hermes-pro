from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ControlDecision:
    allowed: bool
    reason: str


class ControlService:
    def __init__(self, settings: Mapping[str, object] | None = None) -> None:
        self._settings = dict(settings or {})
        self._switches: dict[str, bool] = {}

    def set_kill_switch(self, name: str, enabled: bool) -> None:
        self._switches[name] = enabled

    def get_status(self) -> dict[str, object]:
        return {"kill_switches": dict(self._switches), "settings": dict(self._settings)}

    def is_allowed(self, action: str, estimated_cost: float = 0.0) -> ControlDecision:
        if self._switches.get("global", False):
            return ControlDecision(False, "global kill switch enabled")
        if self._switches.get(action, False):
            return ControlDecision(False, f"kill switch enabled: {action}")
        budget = float(self._settings.get("daily_budget", 0.0) or 0.0)
        spent = float(self._settings.get("daily_spend", 0.0) or 0.0)
        if budget > 0 and spent + max(0.0, estimated_cost) > budget:
            return ControlDecision(False, "daily budget exceeded")
        return ControlDecision(True, "allowed")
