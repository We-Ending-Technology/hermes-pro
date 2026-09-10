from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from ..core.config import Settings


class HotmartError(RuntimeError):
    pass


class HotmartClient:
    def __init__(self, settings: Settings) -> None:
        self.client_id = settings.hotmart_client_id
        self.client_secret = settings.hotmart_client_secret
        self._token: str | None = None
        self._expires_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def access_token(self) -> str:
        if not self.configured:
            raise HotmartError("HOTMART_CLIENT_ID and HOTMART_CLIENT_SECRET are required")
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api-sec-vlc.hotmart.com/security/oauth/token",
                params={"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret},
                headers={"Authorization": f"Basic {basic}", "Content-Type": "application/json"},
            )
        if response.is_error:
            raise HotmartError(f"Hotmart OAuth failed: {response.status_code} {response.text[:400]}")
        data = response.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._token

    async def list_products(self) -> list[dict[str, Any]]:
        token = await self.access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://developers.hotmart.com/products/api/v1/products",
                params={"max_results": 50},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if response.is_error:
            raise HotmartError(f"Hotmart products failed: {response.status_code} {response.text[:400]}")
        return response.json().get("items", [])

    async def list_offers(self, ucode: str) -> list[dict[str, Any]]:
        token = await self.access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"https://developers.hotmart.com/products/api/v1/products/{ucode}/offers",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if response.is_error:
            raise HotmartError(f"Hotmart offers failed: {response.status_code} {response.text[:400]}")
        return response.json().get("items", [])
