from __future__ import annotations

from typing import Any

from .base import Agent
from .autonomous import CommerceAgent, AGENT_NAMES


class PassThroughAgent(Agent):
    """Compatibility agent for registry names not yet mapped to a concrete agent."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "not_implemented",
            "agent": self.name,
            "input": input_data,
        }


__all__ = ["CommerceAgent", "AGENT_NAMES", "PassThroughAgent"]
