import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from .base import AIGateway, AIResponse


_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 5
logger = logging.getLogger(__name__)


async def _post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    json: dict,
    max_attempts: int = _MAX_ATTEMPTS,
) -> httpx.Response:
    """Retry transient provider failures up to five total attempts."""
    for attempt in range(max_attempts):
        try:
            response = await client.post(url, headers=headers, json=json)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in _RETRYABLE_STATUS_CODES or attempt >= max_attempts - 1:
                raise

            retry_after = exc.response.headers.get("Retry-After")
            delay = min(2**attempt, 8)
            if retry_after:
                try:
                    delay = min(max(float(retry_after), 0.0), 60.0)
                except ValueError:
                    try:
                        retry_at = parsedate_to_datetime(retry_after)
                        if retry_at.tzinfo is None:
                            retry_at = retry_at.replace(tzinfo=timezone.utc)
                        delay = min(max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0.0), 60.0)
                    except (TypeError, ValueError, OverflowError):
                        pass
            await asyncio.sleep(delay + random.uniform(0.0, min(delay * 0.2, 0.5)))
        except httpx.TransportError:
            # DNS, connect, read, write and protocol interruptions are transient
            # in many hosted environments. Retry them without retrying 4xx errors.
            if attempt >= max_attempts - 1:
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

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "default",
        *,
        circuit_failure_threshold: int = 5,
        circuit_open_seconds: float = 60.0,
        timeout_seconds: float = 45.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model)
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_open_seconds = circuit_open_seconds
        self.timeout_seconds = timeout_seconds
        self._consecutive_transient_failures = 0
        self._circuit_open_until = 0.0

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        started = time.perf_counter()
        now = time.monotonic()
        if now < self._circuit_open_until:
            remaining = max(1, int(self._circuit_open_until - now))
            raise RuntimeError(
                f"Gemini temporariamente indisponível; circuit breaker aberto por mais {remaining}s."
            )

        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\\n{system}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds, connect=min(10.0, self.timeout_seconds))) as client:
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
            duration_ms = round((time.perf_counter() - started) * 1000)
            self._consecutive_transient_failures = 0
            self._circuit_open_until = 0.0
            logger.info("ai_request provider=gemini model=%s duration_ms=%s outcome=success", self.model, duration_ms)
            return AIResponse(content=text, provider=self.provider, model=self.model)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _RETRYABLE_STATUS_CODES:
                self._consecutive_transient_failures += 1
                if self._consecutive_transient_failures >= self.circuit_failure_threshold:
                    self._circuit_open_until = time.monotonic() + self.circuit_open_seconds
            duration_ms = round((time.perf_counter() - started) * 1000)
            logger.error("ai_request provider=gemini model=%s duration_ms=%s outcome=error status=%s consecutive_failures=%s", self.model, duration_ms, exc.response.status_code, self._consecutive_transient_failures)
            raise RuntimeError("IA indisponível: Gemini falhou após as tentativas configuradas.") from exc
        except httpx.TransportError as exc:
            self._consecutive_transient_failures += 1
            if self._consecutive_transient_failures >= self.circuit_failure_threshold:
                self._circuit_open_until = time.monotonic() + self.circuit_open_seconds
            duration_ms = round((time.perf_counter() - started) * 1000)
            logger.error("ai_request provider=gemini model=%s duration_ms=%s outcome=transport_error error=%s consecutive_failures=%s", self.model, duration_ms, type(exc).__name__, self._consecutive_transient_failures)
            raise RuntimeError("IA indisponível: falha de comunicação com Gemini.") from exc


class GroqAdapter(ConfiguredProviderAdapter):
    provider = "groq"

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_completion_tokens": 2048,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = await _post_with_retries(
                client,
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            data = response.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Groq returned an unexpected response") from exc
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Groq returned no message content")
        return AIResponse(content=text, provider=self.provider, model=self.model)

