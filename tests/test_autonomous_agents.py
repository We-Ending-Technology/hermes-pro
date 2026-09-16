import pytest

from backend.app.agents.autonomous import AGENT_CAPABILITIES, AGENT_NAMES, CommerceAgent
from backend.app.agents.registry import AgentRegistry


class FakeGateway:
    async def complete(self, task, system):
        return type("Result", (), {"content": "ok", "provider": "test", "model": "test"})()


def test_registry_role_roster_contains_operational_agents():
    expected = {"core", "opportunity", "product", "service", "qa", "optimizer", "guardian"}
    assert expected.issubset(set(AGENT_NAMES))
    for name in expected:
        assert AGENT_CAPABILITIES[name]


@pytest.mark.asyncio
async def test_guardian_blocks_publish_when_controls_deny():
    agent = CommerceAgent("guardian", FakeGateway())
    result = await agent.run({"action": "publish", "controls": {"kill_switch": True}})
    assert result["status"] == "blocked"
    assert result["reason"] == "global_kill_switch"


@pytest.mark.asyncio
async def test_non_guardian_agent_returns_explicit_execution_result():
    agent = CommerceAgent("opportunity", FakeGateway())
    result = await agent.run({"task": "evaluate a product opportunity"})
    assert result["status"] == "completed"
    assert result["stage"] == "opportunity"
    assert result["capabilities"] == AGENT_CAPABILITIES["opportunity"]


def test_registry_can_register_all_commerce_roles():
    registry = AgentRegistry()
    for name in AGENT_NAMES:
        registry.register(CommerceAgent(name, FakeGateway()))
    assert set(registry.names()) == set(AGENT_NAMES)
