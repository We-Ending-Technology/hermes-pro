from typing import Any
from .base import Agent

class PassThroughAgent(Agent):
    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"stage": self.name, "input": input_data, "status": "stub"}

AGENT_NAMES = ("writer", "reviewer", "publisher", "supervisor", "diagnostics", "evolution")
