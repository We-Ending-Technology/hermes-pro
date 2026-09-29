from .base import AIGateway, AIResponse
from .stub import StubAIGateway
from .adapters import GeminiAdapter, OpenAIAdapter
from ..core.config import Settings

class FallbackGateway(AIGateway):
    def __init__(self, primary: AIGateway, fallback: AIGateway):
        self.primary = primary
        self.fallback = fallback

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        try:
            return await self.primary.complete(prompt, system=system)
        except Exception as primary_error:
            try:
                return await self.fallback.complete(prompt, system=system)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"AI Gateway unavailable: primary={primary_error}; fallback={fallback_error}"
                ) from fallback_error

def build_ai_gateway(settings: Settings) -> AIGateway:
    gemini = GeminiAdapter(api_key=settings.gemini_api_key or settings.ai_api_key, model=settings.gemini_model)
    openai = OpenAIAdapter(api_key=settings.openai_api_key, model=settings.openai_model)
    if settings.ai_provider == "openai":
        return FallbackGateway(openai, gemini)
    if settings.ai_provider == "stub":
        return StubAIGateway()
    return FallbackGateway(gemini, openai)
