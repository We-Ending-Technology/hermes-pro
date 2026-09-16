import pytest

from backend.app.ai_gateway.base import AIGateway, AIResponse
from backend.app.ai_gateway.failover import FailoverAIGateway, ProviderSlot


class FakeGateway(AIGateway):
    def __init__(self, provider, result=None, error=None):
        self.provider = provider
        self.result = result
        self.error = error
        self.calls = 0

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        self.calls += 1
        if self.error:
            raise self.error
        return AIResponse(content=self.result or "ok", provider=self.provider, model="test")


@pytest.mark.asyncio
async def test_failover_uses_next_slot_after_failure():
    first = FakeGateway("gemini", error=RuntimeError("rate limited"))
    second = FakeGateway("gemini", result="fallback")
    gateway = FailoverAIGateway([
        ProviderSlot("gemini", 1, first),
        ProviderSlot("gemini", 2, second),
    ])

    result = await gateway.complete("hello")

    assert result.content == "fallback"
    assert first.calls == 1
    assert second.calls == 1


@pytest.mark.asyncio
async def test_failover_reaches_next_provider():
    gemini = FakeGateway("gemini", error=RuntimeError("unavailable"))
    openai = FakeGateway("openai", result="openai result")
    gateway = FailoverAIGateway([
        ProviderSlot("gemini", 1, gemini),
        ProviderSlot("openai", 1, openai),
    ])

    result = await gateway.complete("hello")

    assert result.provider == "openai"
    assert openai.calls == 1


@pytest.mark.asyncio
async def test_failover_reports_all_slots_without_exposing_secrets():
    gateway = FailoverAIGateway([
        ProviderSlot("gemini", 1, FakeGateway("gemini", error=ValueError("bad key"))),
        ProviderSlot("openai", 1, FakeGateway("openai", error=TimeoutError())),
    ])

    with pytest.raises(RuntimeError) as exc:
        await gateway.complete("hello")

    message = str(exc.value)
    assert "gemini[1]: ValueError" in message
    assert "openai[1]: TimeoutError" in message
    assert "bad key" not in message
