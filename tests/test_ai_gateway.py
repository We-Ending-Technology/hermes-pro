import httpx
import pytest

from backend.app.ai_gateway.adapters import GeminiAdapter, GroqAdapter, _post_with_retries
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


@pytest.mark.asyncio
async def test_gemini_requests_json_mode_and_sufficient_output_tokens(monkeypatch):
    captured = {}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]},
                request=request,
            )

    monkeypatch.setattr(
        "backend.app.ai_gateway.adapters.httpx.AsyncClient",
        lambda timeout: FakeAsyncClient(),
    )
    result = await GeminiAdapter(api_key="test-key", model="gemini-3.5-flash-lite").complete(
        "Return a JSON object", system="Only JSON"
    )
    assert result.content == '{"ok": true}'
    assert captured["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert captured["json"]["generationConfig"]["maxOutputTokens"] == 8192
    assert captured["json"]["generationConfig"]["temperature"] == 0.2

@pytest.mark.asyncio
async def test_provider_request_retries_transient_transport_error(monkeypatch):
    calls = 0
    delays = []

    async def no_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("backend.app.ai_gateway.adapters.asyncio.sleep", no_sleep)
    monkeypatch.setattr("backend.app.ai_gateway.adapters.random.uniform", lambda _a, _b: 0)

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("temporary connection failure", request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await _post_with_retries(client, "https://provider.test", headers={}, json={})

    assert response.status_code == 200
    assert calls == 2
    assert delays == [1]

@pytest.mark.asyncio
async def test_groq_adapter_uses_compatible_chat_completions_api(monkeypatch):
    captured = {}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"answer": "ok"}'}}]},
                request=request,
            )

    monkeypatch.setattr(
        "backend.app.ai_gateway.adapters.httpx.AsyncClient",
        lambda timeout: FakeAsyncClient(),
    )
    result = await GroqAdapter(api_key="test-groq-key", model="openai/gpt-oss-20b").complete(
        "Return a JSON object", system="Only JSON"
    )
    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-20b"
    assert result.content == '{"answer": "ok"}'
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-groq-key"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["max_completion_tokens"] == 2048



@pytest.mark.asyncio
async def test_gemini_circuit_breaker_opens_after_five_transient_failures(monkeypatch):
    import backend.app.ai_gateway.adapters as adapters

    now = 100.0
    calls = 0

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def always_rate_limited(*args, **kwargs):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com/test")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(adapters.httpx, "AsyncClient", lambda timeout: FakeAsyncClient())
    monkeypatch.setattr(adapters, "_post_with_retries", always_rate_limited)
    monkeypatch.setattr(adapters.time, "monotonic", lambda: now)

    gateway = GeminiAdapter(api_key="test-key", model="gemini-test")
    for _ in range(5):
        with pytest.raises(RuntimeError, match="IA indisponível"):
            await gateway.complete("test")

    assert calls == 5
    with pytest.raises(RuntimeError, match="circuit breaker aberto"):
        await gateway.complete("test")
    assert calls == 5

    now += 61
    with pytest.raises(RuntimeError, match="IA indisponível"):
        await gateway.complete("test")
    assert calls == 6
