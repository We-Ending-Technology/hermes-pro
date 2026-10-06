from .base import AIGateway
from .stub import StubAIGateway
from .adapters import GeminiAdapter, OpenAIAdapter
from ..core.config import Settings

class FallbackAIGateway(AIGateway):
    def __init__(self, primary: AIGateway, fallback: AIGateway | None) -> None:
        self.primary = primary
        self.fallback = fallback

    async def complete(self, prompt: str, *, system: str | None = None):
        try:
            return await self.primary.complete(prompt, system=system)
        except Exception as primary_error:
            if self.fallback is None:
                raise
            try:
                return await self.fallback.complete(prompt, system=system)
            except Exception as fallback_error:
                raise RuntimeError(f"AI providers unavailable: primary={primary_error}; fallback={fallback_error}") from fallback_error

def build_ai_gateway(settings: Settings) -> AIGateway:
    if settings.ai_provider == "gemini":
        primary = GeminiAdapter(api_key=settings.gemini_api_key or settings.ai_api_key, model=settings.gemini_model)
    elif settings.ai_provider == "openai":
        primary = OpenAIAdapter(api_key=settings.openai_api_key, model=settings.openai_chat_model)
    elif settings.ai_provider == "stub":
        return StubAIGateway()
    else:
        raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")

    fallback = None
    if settings.ai_fallback_provider == "openai" and settings.openai_api_key and settings.ai_provider != "openai":
        fallback = OpenAIAdapter(api_key=settings.openai_api_key, model=settings.openai_chat_model)
    elif settings.ai_fallback_provider == "gemini" and (settings.gemini_api_key or settings.ai_api_key) and settings.ai_provider != "gemini":
        fallback = GeminiAdapter(api_key=settings.gemini_api_key or settings.ai_api_key, model=settings.gemini_model)
    return FallbackAIGateway(primary, fallback)
