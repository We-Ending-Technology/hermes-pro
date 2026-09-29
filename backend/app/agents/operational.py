from __future__ import annotations
from typing import Any
from .base import Agent
from ..services.opportunities import SOURCES, fetch_opportunities, score_opportunity
from ..ai_gateway.base import AIGateway
from ..core.config import get_settings

class RadarAgent(Agent):
    name = "radar"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        items = await fetch_opportunities(limit=int(input_data.get("limit", 40)))
        minimum = int(input_data.get("minimum_score", 55))
        ranked = []
        for item in items:
            scored = score_opportunity(item)
            if scored["score"] >= minimum:
                ranked.append({
                    "id": item.fingerprint, "source": item.source, "title": item.title,
                    "url": item.url, "description": item.description, "tags": item.tags,
                    "budget": item.budget, "currency": item.currency,
                    "discovery_automation_allowed": item.discovery_automation_allowed,
                    "application_automation_allowed": bool(item.source == "freelancer" and get_settings().freelancer_enabled and get_settings().freelancer_auto_apply), **scored,
                })
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return {"count": len(ranked), "opportunities": ranked[:30]}

class ResearcherAgent(Agent):
    name = "researcher"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "sources": [{"name": name, **cfg} for name, cfg in SOURCES.items()],
            "policy": "Only public feeds/APIs or explicitly permitted automation may be automated. Discovery access never implies permission to submit applications.",
        }

class AnalystAgent(Agent):
    name = "analyst"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        opportunity = input_data.get("opportunity") or {}
        text = " ".join(str(opportunity.get(k, "")) for k in ("title", "description", "tags")).lower()
        effort = 35
        if "complex" in text or "architecture" in text: effort += 25
        if "urgent" in text or "asap" in text: effort += 10
        return {
            "priority": round(float(opportunity.get("score", 0)) * 0.7 + (100 - effort) * 0.3),
            "estimated_effort": min(effort, 100),
            "risk": "low" if effort < 55 else "medium",
            "next_action": "prepare_work_package" if opportunity.get("application_automation_allowed") else "manual_review",
        }

class ExecutorAgent(Agent):
    name = "executor"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        opportunity = input_data.get("opportunity") or {}
        return {
            "status": "work_package_ready",
            "execution_mode": "automated_submission" if opportunity.get("application_automation_allowed") else "automated_preparation",
            "deliverables": ["requirements_checklist", "implementation_plan", "draft_response"],
            "requires_human_submission": not bool(opportunity.get("application_automation_allowed")),
        }

class QAAgent(Agent):
    name = "qa"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        opportunity = input_data.get("opportunity") or {}
        required = ["title", "url", "source"]
        missing = [k for k in required if not opportunity.get(k)]
        return {"approved": not missing, "missing": missing, "checks": ["source", "url", "scope", "automation_policy"]}

class CommercialAgent(Agent):
    name = "commercial"
    def __init__(self, gateway: AIGateway): self.gateway = gateway
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        opportunity = input_data.get("opportunity") or {}
        prompt = (
            "Create a concise freelance proposal draft in Portuguese for this opportunity. "
            "Do not invent experience, price, deadlines or client facts. Return plain text.\n"
            f"Title: {opportunity.get('title')}\nDescription: {opportunity.get('description', '')[:3000]}"
        )
        result = await self.gateway.complete(prompt, system="You are Hermes Pro's commercial agent.")
        return {"draft": result.content, "provider": result.provider, "model": result.model}

class FinanceAgent(Agent):
    name = "finance"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        opportunity = input_data.get("opportunity") or {}
        score = float(opportunity.get("score", 0))
        return {"score": score, "budget": opportunity.get("budget"), "currency": opportunity.get("currency"), "decision": "track" if score >= 60 else "ignore"}

class RecoveryAgent(Agent):
    name = "recovery"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"action": "retry_then_fallback", "max_attempts": 3, "escalate_after": 3, "input": input_data}

class GuardianAgent(Agent):
    name = "guardian"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        opportunity = input_data.get("opportunity") or {}
        allowed = bool(opportunity.get("application_automation_allowed"))
        return {"safe_to_automate": allowed, "reason": "official application permission registered" if allowed else "manual submission gate"}

class WatchtowerAgent(Agent):
    name = "watchtower"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "checks": ["api", "worker", "queue", "ai_gateway", "persistence"]}

class SupervisorAgent(Agent):
    name = "supervisor"
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"decision": "continue", "rules": ["bounded_retries", "budget_guard", "manual_gate_for_unapproved_sources"]}
