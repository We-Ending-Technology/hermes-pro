from typing import Any

from .base import Agent


class PassThroughAgent(Agent):
    """Compatibility agent used only when autonomous AI is not configured."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"stage": self.name, "input": input_data, "status": "blocked_missing_OPENAI_API_KEY"}


class SDKBackedAgent(Agent):
    """Adapter that exposes an OpenAI Agents SDK agent through Hermes' stable interface."""

    def __init__(self, name: str, sdk_agent: Any) -> None:
        self.name = name
        self.sdk_agent = sdk_agent

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        from agents import Runner

        prompt = str(input_data.get("prompt", input_data))
        result = await Runner.run(self.sdk_agent, prompt)
        return {
            "stage": self.name,
            "status": "completed",
            "output": result.final_output,
            "agent": result.last_agent.name,
            "steps": len(result.new_items),
        }


AGENT_NAMES = ("writer", "reviewer", "publisher", "supervisor", "diagnostics", "evolution")
