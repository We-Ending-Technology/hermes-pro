from .base import Agent

class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(f"Agent not registered: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._agents)
