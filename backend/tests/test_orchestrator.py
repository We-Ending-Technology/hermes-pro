import pytest

from app.agents.orchestrator import AgentOrchestrator


def test_orchestrator_dispatches_bounded_agent():
    result = AgentOrchestrator().run("Radar", {"topic": "x"})
    assert result.status == "completed"
    assert result.agent == "Radar"


def test_orchestrator_rejects_unknown_agent():
    with pytest.raises(KeyError):
        AgentOrchestrator().run("Unknown", {})
