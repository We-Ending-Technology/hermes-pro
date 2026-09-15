from __future__ import annotations

from typing import Any

from .base import Agent


class CommerceAgent(Agent):
    def __init__(self, name: str, ai_gateway: Any) -> None:
        self.name = name
        self.ai_gateway = ai_gateway

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        task = input_data.get("task") or input_data.get("message") or str(input_data)
        result = await self.ai_gateway.complete(
            str(task),
            system=(
                f"You are the Hermes {self.name} agent. Execute only the requested operational analysis. "
                "Return concise structured JSON-like text. Never invent external results, sales, prices, "
                "credentials, publication status, or completed actions. Clearly mark assumptions and missing data."
            ),
        )
        return {"stage": self.name, "status": "completed", "output": result.content, "provider": result.provider, "model": result.model}


AGENT_NAMES = ("writer", "reviewer", "publisher", "supervisor", "diagnostics", "evolution")
