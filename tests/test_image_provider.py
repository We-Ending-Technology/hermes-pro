import pytest
from backend.app.image_provider import ImageProvider, ImageResult


class FakeImageProvider(ImageProvider):
    provider = "fake"

    async def generate_cover(self, prompt: str) -> ImageResult:
        return ImageResult(url="https://example.invalid/cover.png", provider=self.provider)


@pytest.mark.asyncio
async def test_image_provider_contract() -> None:
    result = await FakeImageProvider().generate_cover("ebook cover")
    assert result.provider == "fake"
    assert result.url.startswith("https://")
