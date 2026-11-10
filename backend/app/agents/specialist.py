from __future__ import annotations

from typing import Any

from .base import Agent
from ..ai_gateway.base import AIGateway


class SpecialistAgent(Agent):
    def __init__(self, name: str, instructions: str, gateway: AIGateway) -> None:
        self.name = name
        self.instructions = instructions
        self.gateway = gateway

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        prompt = str(input_data.get("prompt", "")).strip()
        if not prompt:
            raise ValueError(f"{self.name} requires a non-empty prompt")
        response = await self.gateway.complete(
            f"Tarefa recebida do Hermes Chefe:\n{prompt}\n\n"
            "Entregue análise objetiva, fatos, hipóteses, riscos e ações recomendadas. "
            "Não afirme que executou ações externas.",
            system=f"{self.instructions} Você integra o time Hermes Pro. Seja conciso e verificável.",
        )
        return {
            "agent": self.name,
            "analysis": response.content,
            "provider": response.provider,
            "model": response.model,
        }


class ChiefAgent(Agent):
    name = "Hermes Chefe"

    def __init__(self, settings) -> None:
        self.settings = settings

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        from .orchestrator import run_chief

        prompt = str(input_data.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("Hermes Chefe requires a non-empty prompt")
        return await run_chief(prompt, self.settings)
