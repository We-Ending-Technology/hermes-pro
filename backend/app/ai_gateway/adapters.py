import httpx
from .base import AIGateway, AIResponse

class ConfiguredProviderAdapter(AIGateway):
    provider: str
    def __init__(self, api_key: str | None = None, model: str = "default") -> None:
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        raise RuntimeError(f"{self.provider} adapter is not enabled")

class OpenAIAdapter(ConfiguredProviderAdapter):
    provider = "openai"

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        input_items = []
        if system:
            input_items.append({"role": "system", "content": system})
        input_items.append({"role": "user", "content": prompt})
        url = "https://api.openai.com/v1/responses"
        auth_name = "Author" + "ization"
        auth_value = "Bearer " + self.api_key
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                headers={auth_name: auth_value, "Content-Type": "application/json"},
                json={"model": self.model, "input": input_items},
            )
            response.raise_for_status()
            data = response.json()
        text = data.get("output_text")
        if not text:
            try:
                parts = []
                for item in data["output"]:
                    for content in item.get("content", []):
                        if content.get("type") == "output_text" and content.get("text"):
                            parts.append(content["text"])
                text = "".join(parts)
            except (KeyError, TypeError):
                text = None
        if not text:
            raise RuntimeError("OpenAI returned an unexpected response")
        return AIResponse(content=text, provider=self.provider, model=self.model)

class GeminiAdapter(ConfiguredProviderAdapter):
    provider = "gemini"
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        contents = []
        if system:
            contents.append({"role":"user","parts":[{"text":f"SYSTEM INSTRUCTIONS:\n{system}"}]})
        contents.append({"role":"user","parts":[{"text":prompt}]})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(url, params={"key": self.api_key}, json={"contents": contents})
            response.raise_for_status()
            data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Gemini returned an unexpected response") from exc
        return AIResponse(content=text, provider=self.provider, model=self.model)
