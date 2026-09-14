import asyncio

from backend.app.ai_gateway.adapters import OpenAIAdapter
from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import Settings


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "ebook test response"}],
                }
            ]
        }


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, headers=None, json=None):
        assert url == "https://api.openai.com/v1/responses"
        assert headers["Authorization"] == "Bearer test-key"
        assert json["model"] == "gpt-5.6-luna"
        assert json["input"][0]["role"] == "system"
        assert json["input"][1]["role"] == "user"
        return FakeResponse()


def test_openai_adapter_uses_responses_api(monkeypatch):
    import backend.app.ai_gateway.adapters as adapters

    monkeypatch.setattr(adapters.httpx, "AsyncClient", FakeAsyncClient)
    result = asyncio.run(
        OpenAIAdapter(api_key="test-key", model="gpt-5.6-luna").complete(
            "Write a short ebook outline", system="You are Hermes Pro."
        )
    )
    assert result.content == "ebook test response"
    assert result.provider == "openai"
    assert result.model == "gpt-5.6-luna"


def test_factory_builds_openai_provider():
    settings = Settings(AI_PROVIDER="openai", AI_API_KEY="test-key")
    gateway = build_ai_gateway(settings)
    assert isinstance(gateway, OpenAIAdapter)
    assert gateway.api_key == "test-key"
    assert gateway.model == "gpt-5.6-luna"
