import pytest

from backend.app.ai_gateway.base import AIGateway, AIResponse
from backend.app.ai_gateway.factory import FallbackGateway

class BrokenGateway(AIGateway):
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        raise RuntimeError("primary failed")

class WorkingGateway(AIGateway):
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        return AIResponse(content="fallback ok", provider="test", model="test-model")

@pytest.mark.asyncio
async def test_fallback_gateway_uses_fallback_after_primary_error():
    result = await FallbackGateway(BrokenGateway(), WorkingGateway()).complete("hello")
    assert result.content == "fallback ok"
    assert result.provider == "test"
