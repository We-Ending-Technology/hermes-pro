import asyncio
import random

import httpx

from .base import AIGateway, AIResponse


_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_MAX_RETRIES = 3


async def _post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    json: dict,
) -> httpx.Response:
    """Retry transient provider failures without retrying invalid requests or credentials."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.post(url, headers=headers, json=json)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in _RETRYABLE_STATUS_CODES or attempt >= _MAX_RETRIES:
                raise

            retry_after = exc.response.headers.get("Retry-After")
            try:
                delay = min(max(float(retry_after), 0.0), 30.0) if retry_after else min(2**attempt, 8)
            except ValueError:
                delay = min(2**attempt, 8)
            await asyncio.sleep(delay + random.uniform(0.0, min(delay * 0.2, 0.5)))
        except httpx.TransportError:
            # DNS, connect, read, write and protocol interruptions are transient
            # in many hosted environments. Retry them without retrying 4xx errors.
            if attempt >= _MAX_RETRIES:
                raise
            delay = min(2**attempt, 8)
            await asyncio.sleep(delay + random.uniform(0.0, min(delay * 0.2, 0.5)))

    raise RuntimeError("AI provider request exhausted retries")


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
        payload = {"model": self.model, "input": prompt}
        if system:
            payload["instructions"] = system
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await _post_with_retries(
                client, "https://api.openai.com/v1/responses", headers=headers, json=payload
            )
            data = response.json()
        text = data.get("output_text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("OpenAI returned no output_text")
        return AIResponse(content=text, provider=self.provider, model=self.model)


class GeminiAdapter(ConfiguredProviderAdapter):
    provider = "gemini"

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\\n{system}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = await _post_with_retries(
                client,
                url,
                headers=headers,
                json={
                    "contents": contents,
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.2,
                        "maxOutputTokens": 8192,
                    },
                },
            )
            data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Gemini returned an unexpected response") from exc
        return AIResponse(content=text, provider=self.provider, model=self.model)
