from .base import AIGateway
from .stub import StubAIGateway
from .gemini import GeminiGateway
from ..core.config import Settings

def build_ai_gateway(settings: Settings) -> AIGateway:
    if settings.ai_provider == "stub":
        return StubAIGateway()
    if settings.ai_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
        return GeminiGateway(settings.gemini_api_key, settings.gemini_model)
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
