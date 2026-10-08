from .base import AIGateway, AIResponse
from .stub import StubAIGateway
from .adapters import GeminiAdapter, OpenAIAdapter
from ..core.config import Settings


class FallbackAIGateway(AIGateway):
    def __init__(self, primary: AIGateway, fallback: AIGateway | None = None) -> None:
        self.primary = primary
        self.fallback = fallback

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        primary_error: Exception | None = None
        try:
            return await self.primary.complete(prompt, system=system)
        except Exception as exc:
            primary_error = exc
        if self.fallback is not None:
            try:
                return await self.fallback.complete(prompt, system=system)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"AI primary failed: {primary_error}; fallback failed: {fallback_error}"
                ) from fallback_error
        raise RuntimeError(f"AI provider failed: {primary_error}") from primary_error


def build_ai_gateway(settings: Settings) -> AIGateway:
    if settings.ai_provider == "openai":
        primary = OpenAIAdapter(api_key=settings.openai_api_key or settings.ai_api_key, model=settings.openai_model)
        fallback = GeminiAdapter(api_key=settings.gemini_api_key or settings.ai_api_key, model=settings.gemini_model)
    elif settings.ai_provider == "gemini":
        primary = GeminiAdapter(api_key=settings.gemini_api_key or settings.ai_api_key, model=settings.gemini_model)
        fallback = OpenAIAdapter(api_key=settings.openai_api_key or settings.ai_api_key, model=settings.openai_model)
    elif settings.ai_provider == "stub":
        return StubAIGateway()
    else:
        raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
    return FallbackAIGateway(primary, fallback)
