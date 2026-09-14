from datetime import datetime

from .base import AIGateway, AIResponse

class StubAIGateway(AIGateway):
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        lowered = prompt.lower()
        if any(term in lowered for term in ("que horas", "hora agora", "data de hoje", "dia de hoje", "data e hora")):
            now = datetime.now().astimezone()
            content = now.strftime("Agora são %H:%M:%S de %d/%m/%Y (%A), no horário do servidor. O Gemini ainda não está conectado.")
            return AIResponse(content=content, provider="stub", model="deterministic")
        return AIResponse(content=f"Stub response for: {prompt}", provider="stub", model="deterministic")
