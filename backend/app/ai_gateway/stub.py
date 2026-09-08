from .base import AIGateway, AIResponse

class StubAIGateway(AIGateway):
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        return AIResponse(content=f"Stub response for: {prompt}", provider="stub", model="deterministic")
