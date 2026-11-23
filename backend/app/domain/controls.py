from __future__ import annotations

from typing import Any

ACTION_DOMAIN = {
    "publish": "publishing",
    "spend": "spend",
    "produce": "production",
    "service": "services",
    "radar": "radar",
}


def control_allows(action: str, settings: dict[str, Any]) -> tuple[bool, str]:
    if settings.get("kill_switch") is True:
        return False, "global_kill_switch"

    domain = ACTION_DOMAIN.get(action)
    paused = settings.get("paused_domains") or []
    if domain and domain in paused:
        return False, "domain_paused"

    budget = settings.get("daily_ai_budget")
    spend = settings.get("daily_ai_spend")
    if budget is not None and spend is not None and float(spend) >= float(budget):
        return False, "budget_exceeded"

    return True, "allowed"
