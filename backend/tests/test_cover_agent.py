import io

from PIL import Image

from backend.app.api_covers import _validate_cover
from backend.app.services.artifacts import build_cover


def test_cover_agent_composes_and_validates_vertical_png():
    artwork = io.BytesIO()
    Image.new("RGB", (512, 512), "#315b72").save(artwork, format="PNG")
    cover = build_cover("Gestão Inteligente de Estoque", "Guia prático para pequenos negócios", artwork.getvalue())
    width, height = _validate_cover(cover)
    assert (width, height) == (1600, 2560)
