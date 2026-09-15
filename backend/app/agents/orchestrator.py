from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

AGENTS = {
    "Radar", "Market Intelligence", "Product", "Service", "Design", "Document",
    "QA/Editor", "Marketplace/Publisher", "Sales", "Analytics", "Optimizer",
    "Guardian", "Watchtower",
}


@dataclass(frozen=True)
class AgentResult:
    run_id: str
    agent: str
    status: str
    output: dict[str, object]


class AgentOrchestrator:
    def run(self, agent: str, context: dict[str, object]) -> AgentResult:
        if agent not in AGENTS:
            raise KeyError(f"unknown agent: {agent}")
        return AgentResult(str(uuid4()), agent, "completed", {"input": context, "mode": "bounded"})
