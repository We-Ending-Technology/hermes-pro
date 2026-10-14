import pytest

from backend.app.agents.stubs import AGENT_NAMES, PassThroughAgent


@pytest.mark.asyncio
async def test_pass_through_agent_never_claims_to_be_ready():
    agent = PassThroughAgent(AGENT_NAMES[0])

    result = await agent.run({"probe": "truthfulness"})

    assert result["status"] == "placeholder"
    assert result["execution_verified"] is False
    assert "no specialized execution handler" in result["message"]
