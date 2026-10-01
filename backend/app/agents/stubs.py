from __future__ import annotations

from typing import Any

from .autonomous import CommerceAgent, AGENT_NAMES
from .base import Agent


class PassThroughAgent(Agent):
    """Compatibility agent for roles that do not yet have a specialized runtime."""

    def __init__(self, agent_name: str) -> None:
        if agent_name not in AGENT_NAMES:
            raise ValueError(f"Unknown Hermes agent role: {agent_name}")
        self.name = agent_name

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "stage": self.name,
            "status": "ready",
            "message": "Agent role registered; no specialized execution handler is configured for this role yet.",
            "input_received": bool(input_data),
        }


__all__ = ["CommerceAgent", "AGENT_NAMES", "PassThroughAgent"]
