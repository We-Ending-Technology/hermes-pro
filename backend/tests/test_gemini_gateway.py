import httpx
import pytest

from backend.app.ai_gateway.adapters import GeminiAdapter


@pytest.mark.asyncio
async def test_gemini_uses_stable_v1_and_returns_text(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

        @property
        def text(self):
            return ""

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    result = await GeminiAdapter(api_key="test-key", model="gemini-3.8-flash").complete("hello")

    assert result.content == "ok"
    assert "/v1/models/gemini-3.8-flash:generateContent" in captured["url"]
    assert captured["kwargs"]["params"] == {"key": "test-key"}


@pytest.mark.asyncio
async def test_gemini_surfaces_provider_error(monkeypatch):
    class FakeResponse:
        status_code = 404
        text = '{"error":{"message":"model not found"}}'

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())

    with pytest.raises(RuntimeError, match="Gemini HTTP 404"):
        await GeminiAdapter(api_key="test-key", model="missing-model").complete("hello")
