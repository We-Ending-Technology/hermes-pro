from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

import httpx

from ..core.config import Settings


class HotmartError(RuntimeError):
    pass


class HotmartAdapter:
    """Read/sales integration plus publication-capability reporting.

    The official public API documents product listing and sales history. It does
    not document a generic creator-product creation endpoint, so this adapter
    never pretends that it can create/publish a new product when that capability
    is not exposed by the account/API.
    """

    token_url = "https://api-sec-vlc.hotmart.com/security/oauth/token"
    api_base = "https://developers.hotmart.com"

    def __init__(self, settings: Settings) -> None:
        self.client_id = settings.hotmart_client_id
        self.client_secret = settings.hotmart_client_secret

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def access_token(self) -> str:
        if not self.configured:
            raise HotmartError("Hotmart credentials are not configured")
        encoded = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {encoded}", "Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.token_url, headers=headers, data={"grant_type": "client_credentials"})
        if response.is_error:
            raise HotmartError(f"Hotmart authentication failed: {response.status_code} {response.text[:300]}")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise HotmartError("Hotmart authentication response has no access_token")
        return token

    async def list_products(self) -> dict[str, Any]:
        token = await self.access_token()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.api_base}/products/api/v1/products", headers={"Authorization": f"Bearer {token}"}, params={"max_results": 50})
        if response.is_error:
            raise HotmartError(f"Hotmart products failed: {response.status_code} {response.text[:300]}")
        return response.json()

    async def sales_history(self, *, product_id: int | None = None, start_date: int | None = None, end_date: int | None = None) -> dict[str, Any]:
        token = await self.access_token()
        params: dict[str, Any] = {"max_results": 50}
        if product_id is not None:
            params["product_id"] = product_id
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.api_base}/payments/api/v1/sales/history", headers={"Authorization": f"Bearer {token}"}, params=params)
        if response.is_error:
            raise HotmartError(f"Hotmart sales failed: {response.status_code} {response.text[:300]}")
        return response.json()

    def publication_capabilities(self) -> dict[str, Any]:
        return {
            "product_create": {"supported": False, "reason": "No generic creator-product creation endpoint was verified in the official public API documentation."},
            "product_list": {"supported": True, "endpoint": "GET /products/api/v1/products"},
            "sales_history": {"supported": True, "endpoint": "GET /payments/api/v1/sales/history"},
            "webhooks": {"supported": True, "reason": "Hotmart provides configurable event notifications."},
            "offer_preparation": {"supported": True, "local": True},
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
