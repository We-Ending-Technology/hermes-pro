import httpx
import pytest

from backend.app.ai_gateway import adapters


@pytest.mark.asyncio
async def test_gemini_opens_circuit_after_five_transient_failures(monkeypatch):
    adapter = adapters.GeminiAdapter(
        api_key="test-key",
        model="gemini-test",
        circuit_failure_threshold=5,
        circuit_open_seconds=60,
    )
    request = httpx.Request("POST", "https://example.test")
    response = httpx.Response(429, request=request)
    failure = httpx.HTTPStatusError("quota", request=request, response=response)

    async def fail_after_retries(*args, **kwargs):
        raise failure

    monkeypatch.setattr(adapters, "_post_with_retries", fail_after_retries)

    for _ in range(5):
        with pytest.raises(RuntimeError, match="IA indisponível"):
            await adapter.complete("test")

    assert adapter._consecutive_transient_failures == 5
    assert adapter._circuit_open_until > adapters.time.monotonic()

    with pytest.raises(RuntimeError, match="circuit breaker aberto"):
        await adapter.complete("must not call provider")


@pytest.mark.asyncio
async def test_retry_after_seconds_is_honored(monkeypatch):
    sleeps = []
    class FakeResponse:
        def raise_for_status(self):
            return None
    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, *args, **kwargs):
            if not hasattr(self, "attempt"):
                self.attempt = 0
            self.attempt += 1
            if self.attempt == 1:
                request = httpx.Request("POST", "https://example.test")
                response = httpx.Response(429, headers={"Retry-After": "3"}, request=request)
                raise httpx.HTTPStatusError("quota", request=request, response=response)
            return FakeResponse()

    monkeypatch.setattr(adapters.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    async def fake_sleep(seconds):
        sleeps.append(seconds)
    monkeypatch.setattr(adapters.asyncio, "sleep", fake_sleep)

    response = await adapters._post_with_retries(
        client=FakeClient(),
        url="https://example.test",
        headers={},
        json={},
        max_attempts=5,
    )

    assert isinstance(response, FakeResponse)
    assert len(sleeps) == 1
    assert 3 <= sleeps[0] <= 3.5
