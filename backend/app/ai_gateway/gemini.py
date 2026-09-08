import httpx
from .base import AIGateway, AIResponse

class GeminiGateway(AIGateway):
    provider = "gemini"
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 30.0) -> None:
        self.api_key, self.model, self.timeout = api_key, model, timeout

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"System instruction: {system}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params={"key": self.api_key}, json={"contents": contents})
            response.raise_for_status()
            data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return AIResponse(content=text, provider=self.provider, model=self.model)
