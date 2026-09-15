from .base import AIGateway
from .stub import StubAIGateway
from .adapters import GeminiAdapter, OpenAIAdapter
from ..core.config import Settings


def build_ai_gateway(settings: Settings) -> AIGateway:
    provider = settings.effective_ai_provider
    if provider == "openai":
        return OpenAIAdapter(api_key=settings.openai_api_key, model=settings.openai_model)
    if provider == "gemini":
        return GeminiAdapter(api_key=settings.gemini_api_key, model=settings.gemini_model)
    if provider == "stub":
        return StubAIGateway()
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
