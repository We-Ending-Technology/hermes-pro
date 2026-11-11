import asyncio
import base64
import io
from types import SimpleNamespace

import httpx
from PIL import Image

from backend.app.services import ai_images
from backend.app.services.ai_images import (
    HORDE_BASE_URL,
    _normalise_image,
    build_cover_prompt,
    generate_cover_artwork,
)
from backend.app.services.artifacts import build_cover


def _png_bytes(size=(512, 512)):
    output = io.BytesIO()
    Image.new("RGB", size, "#527b9a").save(output, format="PNG")
    return output.getvalue()


def test_cover_prompt_uses_book_subject_and_forbids_text():
    prompt = build_cover_prompt(
        "Como Ganhar Dinheiro com IA",
        "Guia prático para iniciantes",
        {
            "chapters": [{"title": "Automação de processos"}],
            "illustrations": [{"description": "Fluxo de automação de tarefas"}],
        },
    )
    assert "Como Ganhar Dinheiro com IA" in prompt
    assert "Automação de processos" in prompt
    assert "no text" in prompt.lower()


def test_normalise_image_returns_valid_png():
    result = _normalise_image(_png_bytes())
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == "PNG"
        assert image.size == (512, 512)


def test_ai_artwork_is_embedded_in_cover():
    cover = build_cover("Guia de exemplo", "Um subtítulo prático", artwork_bytes=_png_bytes())
    with Image.open(io.BytesIO(cover)) as image:
        assert image.format == "PNG"
        assert image.size == (1600, 2560)


async def test_generate_cover_artwork_polls_horde_and_downloads_result(monkeypatch):
    generated = _png_bytes()
    calls = []

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_wait)

    def handler(request):
        calls.append((request.method, str(request.url)))
        if request.method == "POST" and str(request.url).endswith("/generate/async"):
            return httpx.Response(200, json={"id": "job-123"})
        if str(request.url).endswith("/generate/check/job-123"):
            return httpx.Response(200, json={"done": True, "faulted": False})
        if str(request.url).endswith("/generate/status/job-123"):
            return httpx.Response(200, json={"generations": [{"img": "https://images.example/cover.png"}]})
        if str(request.url) == "https://images.example/cover.png":
            return httpx.Response(200, content=generated, headers={"content-type": "image/png"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    settings = SimpleNamespace(
        ai_image_provider="aihorde",
        ai_horde_api_key="0000000000",
        ai_horde_model="stable_diffusion_2.1",
        ai_horde_timeout_seconds=30,
        ai_horde_base_url=HORDE_BASE_URL,
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await generate_cover_artwork(
            "Guia de teste",
            "Subtítulo",
            {"chapters": [], "illustrations": []},
            settings,
            client=client,
        )

    assert result.startswith(bytes.fromhex("89504e470d0a1a0a"))
    assert any(url.endswith("/generate/async") for _, url in calls)
    assert any(url.endswith("/generate/check/job-123") for _, url in calls)
    assert any(url.endswith("/generate/status/job-123") for _, url in calls)



async def test_generate_cover_artwork_uses_free_ovhcloud_endpoint(monkeypatch):
    generated = _png_bytes()
    calls = []

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    monkeypatch.setattr(ai_images, "_OVHCLOUD_LAST_CALL", 0.0)

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(generated).decode("ascii")}]},
        )

    settings = SimpleNamespace(
        ai_image_provider="ovhcloud",
        ovhcloud_image_base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        ovhcloud_image_model="stable-diffusion-xl-base-v10",
        ovhcloud_image_timeout_seconds=90,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_cover_artwork(
            "Guia de teste",
            "Subtítulo",
            {"chapters": [], "illustrations": []},
            settings,
            client=client,
        )

    assert result.startswith(bytes.fromhex("89504e470d0a1a0a"))
    assert len(calls) == 1
    assert str(calls[0].url) == "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/images/generations"
    assert calls[0].headers.get("authorization") is None
    body = __import__("json").loads(calls[0].content)
    assert body["model"] == "stable-diffusion-xl-base-v10"
    assert body["size"] == "1024x1024"
