from .base import AIGateway, AIResponse

class ConfiguredProviderAdapter(AIGateway):
    provider: str
    def __init__(self, api_key: str | None = None, model: str = "default") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        raise RuntimeError(f"{self.provider} adapter is not enabled in foundation mode")

class OpenAIAdapter(ConfiguredProviderAdapter):
    provider = "openai"

class GeminiAdapter(ConfiguredProviderAdapter):
    provider = "gemini"
