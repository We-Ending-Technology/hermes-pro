from .base import AIGateway
from .stub import StubAIGateway
from ..core.config import Settings

def build_ai_gateway(settings: Settings) -> AIGateway:
    if settings.ai_provider == "stub":
        return StubAIGateway()
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
