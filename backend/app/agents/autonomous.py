from __future__ import annotations

from typing import Any

from .base import Agent


AGENT_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "core": ("orchestration", "planning", "delegation", "state_review"),
    "opportunity": ("market_discovery", "opportunity_scoring", "evidence_review"),
    "product": ("product_strategy", "content_planning", "offer_design"),
    "service": ("service_discovery", "briefing_analysis", "execution_planning"),
    "writer": ("content_generation", "ebook_writing", "copywriting"),
    "reviewer": ("content_review", "fact_checking", "quality_review"),
    "qa": ("quality_gate", "file_validation", "publication_readiness"),
    "publisher": ("channel_readiness", "publication_preflight", "status_verification"),
    "sales": ("sales_analysis", "conversion_analysis", "offer_analysis"),
    "analytics": ("revenue_analysis", "cost_analysis", "profit_analysis", "experiment_analysis"),
    "optimizer": ("performance_analysis", "experiment_planning", "next_action_selection"),
    "guardian": ("policy_gate", "budget_gate", "publication_gate", "risk_gate"),
    "supervisor": ("workflow_supervision", "failure_triage", "recovery_review"),
    "diagnostics": ("health_diagnostics", "integration_diagnostics", "incident_analysis"),
    "evolution": ("system_improvement", "process_analysis", "capability_review"),
    "radar": ("signal_discovery", "trend_monitoring", "opportunity_detection"),
    "notifications": ("event_notification", "alert_routing", "delivery_status"),
}

AGENT_NAMES = tuple(AGENT_CAPABILITIES)


class CommerceAgent(Agent):
    def __init__(self, name: str, ai_gateway: Any) -> None:
        if name not in AGENT_CAPABILITIES:
            raise ValueError(f"Unknown Hermes agent role: {name}")
        self.name = name
        self.capabilities = AGENT_CAPABILITIES[name]
        self.ai_gateway = ai_gateway

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        if self.name == "guardian":
            action = str(input_data.get("action") or "").strip().lower()
            controls = input_data.get("controls") or {}
            if controls.get("kill_switch") is True:
                return {"stage": self.name, "status": "blocked", "reason": "global_kill_switch", "capabilities": self.capabilities}
            paused = controls.get("paused_domains") or []
            domains = {"publish": "publishing", "spend": "spend", "produce": "production", "service": "services", "radar": "radar"}
            if domains.get(action) in paused:
                return {"stage": self.name, "status": "blocked", "reason": "domain_paused", "capabilities": self.capabilities}
            budget = controls.get("daily_total_budget")
            spend = controls.get("daily_total_spend")
            if budget is not None and spend is not None and float(spend) >= float(budget):
                return {"stage": self.name, "status": "blocked", "reason": "budget_exceeded", "capabilities": self.capabilities}

        task = input_data.get("task") or input_data.get("message") or str(input_data)
        result = await self.ai_gateway.complete(
            str(task),
            system=(
                f"You are the Hermes {self.name} agent. Execute only the requested operational analysis. "
                f"Your allowed capabilities are: {', '.join(self.capabilities)}. "
                "Do not perform or claim external side effects outside these capabilities. "
                "Never invent external results, sales, prices, credentials, publication status, market evidence, "
                "or completed actions. Clearly mark assumptions and missing data."
            ),
        )
        return {
            "stage": self.name,
            "status": "completed",
            "output": result.content,
            "provider": result.provider,
            "model": result.model,
            "capabilities": self.capabilities,
        }
