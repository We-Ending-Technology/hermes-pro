from backend.app.ai_gateway.adapters import GeminiAdapter
from backend.app.ai_gateway.factory import build_ai_gateway
from backend.app.core.config import Settings


def test_gemini_is_selected_when_openai_is_selected_but_openai_key_is_missing():
    settings = Settings(
        AI_PROVIDER="openai",
        OPENAI_API_KEY=None,
        GEMINI_API_KEY="configured-gemini-key",
        GEMINI_MODEL="gemini-test",
    )

    gateway = build_ai_gateway(settings)

    assert isinstance(gateway, GeminiAdapter)
    assert gateway.api_key == "configured-gemini-key"
    assert gateway.model == "gemini-test"


def test_gemini_is_selected_automatically_when_provider_is_unset():
    settings = Settings(
        AI_PROVIDER="auto",
        OPENAI_API_KEY=None,
        GEMINI_API_KEY="configured-gemini-key",
    )

    gateway = build_ai_gateway(settings)

    assert isinstance(gateway, GeminiAdapter)
