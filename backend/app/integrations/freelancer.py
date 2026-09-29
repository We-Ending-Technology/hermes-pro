from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class FreelancerConfig:
    access_token: str | None
    base_url: str = "https://www.freelancer.com"
    sandbox: bool = False
    enabled: bool = False
    auto_apply: bool = False
    bidder_id: int | None = None
    profile_id: int | None = None

    @property
    def api_base(self) -> str:
        base = self.base_url.rstrip("/")
        return f"{base}/api"


class FreelancerAPIError(RuntimeError):
    pass


class FreelancerAdapter:
    """Small, explicit adapter for the official Freelancer.com API.

    The adapter never enables automatic bidding merely because credentials exist.
    Both integration enablement and FREELANCER_AUTO_APPLY must be enabled.
    """

    source = "freelancer"

    def __init__(self, config: FreelancerConfig, client: httpx.AsyncClient | None = None):
        self.config = config
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "Hermes-Pro/1.0"}
        if self.config.access_token:
            headers["Freelancer-OAuth-V1"] = self.config.access_token
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True)
        try:
            response = await client.request(method, f"{self.config.api_base}{path}", headers=self._headers(), **kwargs)
            if response.status_code >= 400:
                raise FreelancerAPIError(f"Freelancer API HTTP {response.status_code}: {response.text[:500]}")
            data = response.json()
            if not isinstance(data, dict):
                raise FreelancerAPIError("Freelancer API returned a non-object JSON response")
            return data
        finally:
            if owns_client:
                await client.aclose()

    async def self_user(self) -> dict[str, Any]:
        return await self._request("GET", "/users/0.1/self/")

    async def active_projects(self, *, limit: int = 40, query: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": min(max(limit, 1), 100)}
        if query:
            params["query"] = query
        return await self._request("GET", "/projects/0.1/projects/active/", params=params)

    async def get_project(self, project_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/projects/0.1/projects/{project_id}/")

    async def create_bid(self, *, project_id: int | str, amount: float, description: str, period: int = 3) -> dict[str, Any]:
        if not self.config.enabled or not self.config.auto_apply:
            raise FreelancerAPIError("automatic bidding is disabled; enable FREELANCER_ENABLED and FREELANCER_AUTO_APPLY")
        bidder_id = self.config.bidder_id
        if bidder_id is None:
            me = await self.self_user()
            user = (me.get("result") or {}).get("user") or me.get("user") or (me.get("result") or {}).get("self") or {}
            bidder_id = user.get("id")
        if not bidder_id:
            raise FreelancerAPIError("could not determine Freelancer bidder_id from authenticated account")
        payload: dict[str, Any] = {
            "project_id": int(project_id), "bidder_id": int(bidder_id),
            "amount": int(round(amount)), "period": max(1, int(period)),
            "milestone_percentage": 100, "description": description,
        }
        if self.config.profile_id is not None:
            payload["profile_id"] = int(self.config.profile_id)
        return await self._request("POST", "/projects/0.1/bids/", json=payload)

    async def list_project_bids(self, project_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/projects/0.1/projects/{project_id}/bids/")

    async def list_bids(
        self,
        *,
        bidder_id: int | None = None,
        award_status: str | None = None,
        paid_status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": min(max(limit, 1), 100)}
        if bidder_id is not None:
            params["bidders[]"] = bidder_id
        if award_status:
            params["award_statuses[]"] = award_status
        if paid_status:
            params["paid_statuses[]"] = paid_status
        return await self._request("GET", "/projects/0.1/bids/", params=params)

    async def list_project_milestones(self, project_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/projects/0.1/projects/{project_id}/milestones/")

    async def create_milestone_request(
        self,
        *,
        project_id: int | str,
        bid_id: int | str,
        amount: float,
        description: str,
    ) -> dict[str, Any]:
        if not self.config.enabled:
            raise FreelancerAPIError("Freelancer integration is disabled")
        payload = {
            "project_id": int(project_id),
            "bid_id": int(bid_id),
            "amount": int(round(amount)),
            "description": description[:5000],
        }
        return await self._request("POST", "/projects/0.1/milestone_requests/", json=payload)

    async def request_milestone_release(self, milestone_id: int | str) -> dict[str, Any]:
        if not self.config.enabled:
            raise FreelancerAPIError("Freelancer integration is disabled")
        return await self._request(
            "PUT",
            f"/projects/0.1/milestones/{milestone_id}/",
            json={"action": "request_release", "amount": 0, "reason": "task_description", "reason_text": "Hermes Pro delivery submitted"},
        )

    async def get_milestone_payment(self, milestone_id: int | str) -> dict[str, Any]:
        return await self._request("GET", f"/payments/0.1/milestones/{milestone_id}/")


def build_freelancer_adapter(settings: Any) -> FreelancerAdapter:
    base_url = "https://www.sandbox.freelancer.com" if settings.freelancer_sandbox else "https://www.freelancer.com"
    return FreelancerAdapter(FreelancerConfig(
        access_token=settings.freelancer_access_token,
        base_url=base_url,
        sandbox=settings.freelancer_sandbox,
        enabled=settings.freelancer_enabled,
        auto_apply=settings.freelancer_auto_apply,
        bidder_id=settings.freelancer_bidder_id,
        profile_id=settings.freelancer_profile_id,
    ))
