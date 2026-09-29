import httpx
import pytest

from .freelancer import FreelancerAdapter, FreelancerConfig, FreelancerAPIError


@pytest.mark.asyncio
async def test_active_projects_uses_official_api_shape():
    seen = {}

    async def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["oauth"] = request.headers.get("Freelancer-OAuth-V1")
        return httpx.Response(200, json={"result": {"projects": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = FreelancerAdapter(FreelancerConfig(access_token="token"), client=client)
    try:
        result = await adapter.active_projects(limit=20, query="python")
    finally:
        await client.aclose()
    assert result["result"]["projects"] == []
    assert "/api/projects/0.1/projects/active/" in seen["url"]
    assert "query=python" in seen["url"]
    assert seen["oauth"] == "token"


@pytest.mark.asyncio
async def test_create_bid_is_blocked_without_explicit_auto_apply():
    adapter = FreelancerAdapter(FreelancerConfig(access_token="token", enabled=True, auto_apply=False))
    with pytest.raises(FreelancerAPIError, match="automatic bidding is disabled"):
        await adapter.create_bid(project_id=123, amount=100, description="test")
