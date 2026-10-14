from .base import AIGateway
from .stub import StubAIGateway
from .adapters import GeminiAdapter, OpenAIAdapter
from ..core.config import Settings


class FallbackGateway(AIGateway):
    def __init__(self, primary: AIGateway, fallback: AIGateway):
        self.primary = primary
        self.fallback = fallback

    async def complete(self, prompt: str, *, system: str | None = None):
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
    gemini_key = settings.gemini_api_key or settings.ai_api_key
    gemini = GeminiAdapter(api_key=gemini_key, model=settings.gemini_model)
    openai = OpenAIAdapter(api_key=settings.openai_api_key, model=settings.openai_model)
    has_gemini = bool(gemini_key)
    has_openai = bool(settings.openai_api_key)
    provider = (settings.ai_provider or "auto").strip().lower()

    # Prefer the requested provider when configured, but never wrap a missing
    # provider as primary: use the configured alternative directly.
    if provider == "stub":
        return StubAIGateway()
    if provider == "openai":
        if has_openai and has_gemini:
            return FallbackGateway(openai, gemini)
        if has_openai:
            return openai
        if has_gemini:
            return gemini
        return StubAIGateway()
    if provider == "gemini":
        if has_gemini and has_openai:
            return FallbackGateway(gemini, openai)
        if has_gemini:
            return gemini
        if has_openai:
            return openai
        return StubAIGateway()

    # "auto" and unknown provider values choose whichever credential exists.
    if has_gemini and has_openai:
        return FallbackGateway(gemini, openai)
    if has_gemini:
        return gemini
    if has_openai:
        return openai
    return StubAIGateway()
