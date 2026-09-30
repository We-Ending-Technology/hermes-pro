from .base import AIGateway, AIResponse
from .stub import StubAIGateway
from .adapters import GeminiAdapter, OpenAIAdapter
from ..core.config import Settings

class FallbackGateway(AIGateway):
    def __init__(self, primary: AIGateway, fallback: AIGateway) -> None:
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
                    f"AI Gateway indisponível. Primário: {primary_error}. Fallback: {fallback_error}"
                ) from fallback_error

def build_ai_gateway(settings: Settings) -> AIGateway:
    stub = StubAIGateway()
    if settings.ai_provider == "stub":
        return stub
    if settings.ai_provider == "openai":
        primary = OpenAIAdapter(settings.openai_api_key or settings.ai_api_key, settings.openai_model)
        fallback = GeminiAdapter(settings.gemini_api_key, settings.gemini_model) if settings.gemini_api_key else stub
        return FallbackGateway(primary, fallback)
    if settings.ai_provider == "gemini":
        primary = GeminiAdapter(settings.gemini_api_key or settings.ai_api_key, settings.gemini_model)
        fallback = OpenAIAdapter(settings.openai_api_key, settings.openai_model) if settings.openai_api_key else stub
        return FallbackGateway(primary, fallback)
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
