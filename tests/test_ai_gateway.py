import pytest

from backend.app.ai_gateway.base import AIResponse, AIGateway
from backend.app.ai_gateway.factory import FallbackAIGateway


class FailingGateway(AIGateway):
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        raise RuntimeError("primary unavailable")


class WorkingGateway(AIGateway):
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        return AIResponse(content="fallback answer", provider="openai", model="gpt-6-luna")


@pytest.mark.asyncio
async def test_fallback_gateway_uses_secondary_provider():
    gateway = FallbackAIGateway(FailingGateway(), WorkingGateway())
    result = await gateway.complete("hello")
    assert result.provider == "openai"
    assert result.content == "fallback answer"


@pytest.mark.asyncio
async def test_fallback_gateway_preserves_primary_success():
    gateway = FallbackAIGateway(WorkingGateway(), FailingGateway())
    result = await gateway.complete("hello")
    assert result.provider == "openai"
