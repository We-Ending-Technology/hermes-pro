from .base import AIGateway
from .stub import StubAIGateway
from .adapters import GeminiAdapter
from ..core.config import Settings

def build_ai_gateway(settings: Settings) -> AIGateway:
    if settings.ai_provider == "gemini":
        return GeminiAdapter(api_key=settings.gemini_api_key or settings.ai_api_key, model=settings.gemini_model)
    if settings.ai_provider == "stub":
        return StubAIGateway()
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
