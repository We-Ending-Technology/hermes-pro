import httpx
import pytest

from backend.app.services import market_radar


@pytest.mark.asyncio
async def test_google_trends_rss_matching_niche_is_positive(monkeypatch):
    rss = b"""<?xml version="1.0"?>
    <rss xmlns:ht="https://trends.google.com/trending/rss"><channel>
      <item><title>Inteligencia artificial</title><ht:approx_traffic>2000+</ht:approx_traffic><pubDate>Wed, 12 Nov 2026 10:00:00 GMT</pubDate></item>
      <item><title>Futebol brasileiro</title><ht:approx_traffic>1000+</ht:approx_traffic></item>
    </channel></rss>"""

    class Response:
        content = rss
        def raise_for_status(self):
            pass
    class Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(market_radar.httpx, "AsyncClient", lambda **kwargs: Client())
    result = await market_radar.fetch_google_trends_br("inteligencia artificial")

    assert result["demand_exists"] is True
    assert result["matches"][0]["title"] == "Inteligencia artificial"
    assert result["matches"][0]["demand_estimated_floor"] == 2000
    assert result["competition"] is None


@pytest.mark.asyncio
async def test_google_trends_rss_does_not_invent_demand_for_unmatched_niche(monkeypatch):
    rss = b"""<?xml version="1.0"?>
    <rss xmlns:ht="https://trends.google.com/trending/rss"><channel>
      <item><title>Futebol brasileiro</title><ht:approx_traffic>1000+</ht:approx_traffic></item>
    </channel></rss>"""

    class Response:
        content = rss
        def raise_for_status(self):
            pass
    class Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(market_radar.httpx, "AsyncClient", lambda **kwargs: Client())
    result = await market_radar.fetch_google_trends_br("organização de documentos familiares")

    assert result["demand_exists"] is False
    assert result["matches"] == []
