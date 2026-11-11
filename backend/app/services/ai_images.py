from __future__ import annotations

import asyncio
import base64
import io
from typing import Any

import httpx
from PIL import Image


HORDE_BASE_URL = "https://aihorde.net/api/v2"
ANONYMOUS_HORDE_KEY = "0000000000"
OVHCLOUD_BASE_URL = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
_OVHCLOUD_LOCK = asyncio.Lock()
_OVHCLOUD_LAST_CALL = 0.0
MAX_IMAGE_BYTES = 15 * 1024 * 1024


class AIImageError(RuntimeError):
    """Raised when the free AI image provider cannot return a valid image."""


def build_cover_prompt(title: str, subtitle: str, content_data: dict[str, Any]) -> str:
    """Create a topic-grounded artwork prompt; the model must not render typography."""
    chapter_titles = [
        str(chapter.get("title", "")).strip()
        for chapter in (content_data.get("chapters") or [])[:5]
        if isinstance(chapter, dict) and chapter.get("title")
    ]
    illustration_themes = [
        str(item.get("description", "")).strip()
        for item in (content_data.get("illustrations") or [])[:3]
        if isinstance(item, dict) and item.get("description")
    ]
    context = "; ".join((chapter_titles + illustration_themes)[:6])
    return (
        "Create premium editorial cover artwork for a practical nonfiction ebook. "
        f"Subject and title context: {title}. Subtitle: {subtitle}. "
        f"Specific subject details: {context or title}. "
        "Create one clear, sophisticated central visual metaphor that accurately represents this subject. "
        "Professional publishing art direction, polished composition, rich but restrained colors, "
        "excellent lighting, high visual clarity, sophisticated depth, clean negative space, "
        "portrait-book-cover composition. Artwork only: absolutely no text, no letters, no words, "
        "no numbers, no typography, no logos, no watermark, no mockup, no book object, no border."
    )


def _normalise_image(raw: bytes) -> bytes:
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise AIImageError("AI Horde returned an empty or oversized image")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.verify()
        with Image.open(io.BytesIO(raw)) as source:
            image = source.convert("RGB")
            if image.width < 256 or image.height < 256:
                raise AIImageError("AI Horde image resolution is below 256x256")
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except AIImageError:
        raise
    except Exception as exc:
        raise AIImageError("AI Horde response was not a decodable image") from exc


async def _generate_horde_cover_artwork(
    title: str,
    subtitle: str,
    content_data: dict[str, Any],
    settings: Any,
    *,
    client: httpx.AsyncClient | None = None,
) -> bytes:
    """Generate one free SDXL cover image through the volunteer-run AI Horde."""
    api_key = str(getattr(settings, "ai_horde_api_key", None) or ANONYMOUS_HORDE_KEY)
    model = str(getattr(settings, "ai_horde_model", None) or "stable_diffusion_2.1")
    timeout_seconds = max(30, int(getattr(settings, "ai_horde_timeout_seconds", 180)))
    base_url = str(getattr(settings, "ai_horde_base_url", HORDE_BASE_URL)).rstrip("/")
    headers = {
        "apikey": api_key,
        "Client-Agent": "HermesPro:1.0.0:We-Ending-Technology",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": build_cover_prompt(title, subtitle, content_data),
        "params": {
            "width": 512,
            "height": 512,
            "steps": 25,
            "n": 1,
            "cfg_scale": 7.5,
            "sampler_name": "k_euler_a",
        },
        "models": [model],
        "nsfw": False,
        "censor_nsfw": True,
        "r2": True,
    }

    owns_client = client is None
    session = client or httpx.AsyncClient(timeout=30, follow_redirects=True)
    try:
        submitted = await session.post(f"{base_url}/generate/async", headers=headers, json=payload)
        if submitted.is_error:
            raise AIImageError(f"AI Horde submission failed: HTTP {submitted.status_code}")
        try:
            request_id = submitted.json().get("id")
        except (ValueError, AttributeError) as exc:
            raise AIImageError("AI Horde did not return a generation ID") from exc
        if not request_id:
            raise AIImageError("AI Horde did not return a generation ID")

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        while loop.time() < deadline:
            await asyncio.sleep(5)
            check = await session.get(f"{base_url}/generate/check/{request_id}", headers=headers)
            if check.is_error:
                raise AIImageError(f"AI Horde status check failed: HTTP {check.status_code}")
            status = check.json()
            if status.get("faulted"):
                raise AIImageError("AI Horde could not find a compatible volunteer worker")
            if not status.get("done"):
                continue

            result = await session.get(f"{base_url}/generate/status/{request_id}", headers=headers)
            if result.is_error:
                raise AIImageError(f"AI Horde result retrieval failed: HTTP {result.status_code}")
            generations = result.json().get("generations") or []
            image_url = next(
                (str(item.get("img")) for item in generations if isinstance(item, dict) and item.get("img")),
                None,
            )
            if not image_url:
                raise AIImageError("AI Horde completed without returning an image")
            downloaded = await session.get(image_url)
            if downloaded.is_error:
                raise AIImageError(f"AI Horde image download failed: HTTP {downloaded.status_code}")
            return _normalise_image(downloaded.content)

        raise AIImageError(f"AI Horde generation exceeded the {timeout_seconds}-second time limit")
    except httpx.HTTPError as exc:
        raise AIImageError(f"AI Horde network error: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            await session.aclose()


async def _generate_ovhcloud_cover_artwork(
    title: str,
    subtitle: str,
    content_data: dict[str, Any],
    settings: Any,
    *,
    client: httpx.AsyncClient | None = None,
) -> bytes:
    """Generate a free SDXL image through OVHcloud's anonymous endpoint (2 req/min/IP)."""
    global _OVHCLOUD_LAST_CALL
    model = str(getattr(settings, "ovhcloud_image_model", None) or "stable-diffusion-xl-base-v10")
    base_url = str(getattr(settings, "ovhcloud_image_base_url", OVHCLOUD_BASE_URL)).rstrip("/")
    timeout_seconds = max(30, int(getattr(settings, "ovhcloud_image_timeout_seconds", 90)))
    payload = {
        "model": model,
        "prompt": build_cover_prompt(title, subtitle, content_data),
        "size": "1024x1024",
    }
    owns_client = client is None
    session = client or httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True)
    try:
        async with _OVHCLOUD_LOCK:
            loop = asyncio.get_running_loop()
            wait_seconds = 35 - (loop.time() - _OVHCLOUD_LAST_CALL)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            _OVHCLOUD_LAST_CALL = loop.time()
            response = await session.post(
                f"{base_url}/images/generations",
                headers={"Content-Type": "application/json", "User-Agent": "HermesPro/1.0"},
                json=payload,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "35")
                try:
                    delay = max(35, min(90, int(float(retry_after))))
                except ValueError:
                    delay = 35
                await asyncio.sleep(delay)
                _OVHCLOUD_LAST_CALL = loop.time()
                response = await session.post(
                    f"{base_url}/images/generations",
                    headers={"Content-Type": "application/json", "User-Agent": "HermesPro/1.0"},
                    json=payload,
                )
        if response.is_error:
            raise AIImageError(f"OVHcloud image generation failed: HTTP {response.status_code}")
        try:
            encoded = response.json()["data"][0]["b64_json"]
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIImageError("OVHcloud did not return a valid base64 image") from exc
        return _normalise_image(raw)
    except httpx.HTTPError as exc:
        raise AIImageError(f"OVHcloud image service network error: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            await session.aclose()


async def generate_cover_artwork(
    title: str,
    subtitle: str,
    content_data: dict[str, Any],
    settings: Any,
    *,
    client: httpx.AsyncClient | None = None,
) -> bytes:
    provider = str(getattr(settings, "ai_image_provider", "ovhcloud") or "ovhcloud").strip().lower()
    if provider == "ovhcloud":
        return await _generate_ovhcloud_cover_artwork(
            title, subtitle, content_data, settings, client=client
        )
    if provider == "aihorde":
        return await _generate_horde_cover_artwork(
            title, subtitle, content_data, settings, client=client
        )
    raise AIImageError(f"Unsupported AI_IMAGE_PROVIDER: {provider}")
