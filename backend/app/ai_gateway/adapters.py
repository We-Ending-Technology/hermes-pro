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
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "input": input_items},
            )
            response.raise_for_status()
            data = response.json()
        text = data.get("output_text")
        if not text:
            parts = []
            for item in data.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text" and content.get("text"):
                        parts.append(content["text"])
            text = "".join(parts) or None
        if not text:
            raise RuntimeError("OpenAI returned an unexpected response")
        return AIResponse(content=text, provider=self.provider, model=self.model)


class GeminiAdapter(ConfiguredProviderAdapter):
    provider = "gemini"
    api_base = "https://generativelanguage.googleapis.com/v1"

    async def _available_generate_models(self, client: httpx.AsyncClient) -> list[str]:
        response = await client.get(
            f"{self.api_base}/models",
            headers={"x-goog-api-key": self.api_key or ""},
            params={"pageSize": 100},
        )
        response.raise_for_status()
        data = response.json()
        models: list[str] = []
        for item in data.get("models", []):
            supported = item.get("supportedGenerationMethods") or item.get("supportedActions") or []
            name = str(item.get("name") or "")
            if "generateContent" in supported and name.startswith("models/"):
                models.append(name.removeprefix("models/"))
        return models

    async def _resolve_model(self, client: httpx.AsyncClient, exclude: set[str] | None = None) -> str:
        models = await self._available_generate_models(client)
        excluded = exclude or set()
        candidates = [m for m in models if m not in excluded]
        preferred = ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash")
        for candidate in preferred:
            if candidate in candidates:
                return candidate
        if candidates:
            return candidates[0]
        raise RuntimeError("Nenhum modelo Gemini com generateContent está disponível para esta chave/projeto")

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        body = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        async with httpx.AsyncClient(timeout=90) as client:
            model = self.model
            url = f"{self.api_base}/models/{model}:generateContent"
            response = await client.post(
                url,
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json=body,
            )
            if response.status_code == 404:
                model = await self._resolve_model(client, exclude={model})
                url = f"{self.api_base}/models/{model}:generateContent"
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                    json=body,
                )
            response.raise_for_status()
            data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(str(part.get("text", "")) for part in parts if part.get("text"))
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Gemini returned an unexpected response") from exc
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        return AIResponse(content=text, provider=self.provider, model=model)
