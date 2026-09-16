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
    api_version = "v1"

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        url = f"https://generativelanguage.googleapis.com/{self.api_version}/models/{self.model}:generateContent"
        payload = {"contents": contents}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, params={"key": self.api_key}, json=payload)
            if response.status_code >= 400:
                detail = response.text[:1000]
                raise RuntimeError(f"Gemini HTTP {response.status_code}: {detail}")
            data = response.json()

        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts if part.get("text"))
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Gemini returned an unexpected response: {data!r}") from exc
        if not text.strip():
            raise RuntimeError("Gemini returned an empty response")
        return AIResponse(content=text, provider=self.provider, model=self.model)
