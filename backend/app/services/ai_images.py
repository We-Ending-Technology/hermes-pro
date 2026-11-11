from __future__ import annotations

import asyncio
import io
from typing import Any

import httpx
from PIL import Image


HORDE_BASE_URL = "https://aihorde.net/api/v2"
ANONYMOUS_HORDE_KEY = "0000000000"
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


async def generate_cover_artwork(
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
