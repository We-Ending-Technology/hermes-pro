import httpx
import pytest

from backend.app.ai_gateway.adapters import _post_with_retries
from backend.app.ai_gateway.base import AIResponse, AIGateway
from backend.app.ai_gateway.factory import FallbackAIGateway


class FailingGateway(AIGateway):
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        raise RuntimeError("primary unavailable")


class WorkingGateway(AIGateway):
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        return AIResponse(content="fallback answer", provider="openai", model="gpt-5.5")


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


@pytest.mark.asyncio
async def test_provider_request_retries_transient_503(monkeypatch):
    calls = 0
    delays = []

    async def no_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("backend.app.ai_gateway.adapters.asyncio.sleep", no_sleep)
    monkeypatch.setattr("backend.app.ai_gateway.adapters.random.uniform", lambda _a, _b: 0)

    def handler(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=_request)
        return httpx.Response(200, json={"ok": True}, request=_request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await _post_with_retries(client, "https://provider.test", headers={}, json={})

    assert response.status_code == 200
    assert calls == 2
    assert delays == [1]


@pytest.mark.asyncio
async def test_provider_request_does_not_retry_auth_or_request_errors(monkeypatch):
    calls = 0

    async def no_sleep(_delay):
        pytest.fail("non-retryable response must not sleep")

    monkeypatch.setattr("backend.app.ai_gateway.adapters.asyncio.sleep", no_sleep)

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(401, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await _post_with_retries(client, "https://provider.test", headers={}, json={})

    assert calls == 1
