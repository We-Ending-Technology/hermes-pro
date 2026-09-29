from __future__ import annotations

import asyncio

import httpx

from .base import AIGateway, AIResponse


TRANSIENT_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_DELAYS_SECONDS = (0.4, 1.0)


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

        last_error: Exception | None = None
        for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        url,
                        headers={auth_name: auth_value, "Content-Type": "application/json"},
                        json={"model": self.model, "input": input_items},
                    )
                if response.status_code in TRANSIENT_HTTP_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        f"OpenAI transient HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                data = response.json()
                break
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status not in TRANSIENT_HTTP_STATUS_CODES and not isinstance(
                    exc, (httpx.TimeoutException, httpx.NetworkError)
                ):
                    raise
                if attempt >= len(RETRY_DELAYS_SECONDS):
                    raise RuntimeError(
                        f"OpenAI unavailable after {attempt + 1} attempts"
                    ) from exc
                await asyncio.sleep(RETRY_DELAYS_SECONDS[attempt])
        else:
            raise RuntimeError("OpenAI request failed") from last_error

        text = data.get("output_text")
        if not text:
            try:
                parts = []
                for item in data["output"]:
                    for content_item in item.get("content", []):
                        if content_item.get("type") == "output_text" and content_item.get("text"):
                            parts.append(content_item["text"])
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

        last_error: Exception | None = None
        for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(url, params={"key": self.api_key}, json=payload)
                if response.status_code in TRANSIENT_HTTP_STATUS_CODES:
                    detail = response.text[:1000]
                    raise RuntimeError(f"Gemini HTTP {response.status_code}: {detail}")
                if response.status_code >= 400:
                    detail = response.text[:1000]
                    raise RuntimeError(f"Gemini HTTP {response.status_code}: {detail}")
                data = response.json()
                break
            except (httpx.TimeoutException, httpx.NetworkError, RuntimeError) as exc:
                last_error = exc
                message = str(exc)
                is_transient = (
                    "HTTP 429" in message
                    or "HTTP 500" in message
                    or "HTTP 502" in message
                    or "HTTP 503" in message
                    or "HTTP 504" in message
                    or isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))
                )
                if not is_transient:
                    raise
                if attempt >= len(RETRY_DELAYS_SECONDS):
                    raise RuntimeError(
                        f"Gemini unavailable after {attempt + 1} attempts: {message}"
                    ) from exc
                await asyncio.sleep(RETRY_DELAYS_SECONDS[attempt])
        else:
            raise RuntimeError("Gemini request failed") from last_error

        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts if part.get("text"))
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Gemini returned an unexpected response: {data!r}") from exc
        if not text.strip():
            raise RuntimeError("Gemini returned an empty response")
        return AIResponse(content=text, provider=self.provider, model=self.model)
