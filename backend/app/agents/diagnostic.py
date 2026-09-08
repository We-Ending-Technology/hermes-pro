from typing import Any
from .base import Agent
from ..ai_gateway.base import AIGateway

class DiagnosticAgent(Agent):
    name = "diagnostic"

    def __init__(self, gateway: AIGateway) -> None:
        self.gateway = gateway

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        prompt = str(input_data.get("prompt", "Run a system diagnostic"))
        response = await self.gateway.complete(prompt, system="You are a Hermes Pro diagnostic agent.")
        return {"message": response.content, "provider": response.provider, "model": response.model}
