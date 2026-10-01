from __future__ import annotations

from typing import Any
import base64
import requests


class HotmartError(RuntimeError):
    pass


class HotmartClient:
    """Small Hotmart API client used by Hermes' commercial endpoints."""

    def __init__(self, settings: Any) -> None:
        self.client_id = settings.hotmart_client_id
        self.client_secret = settings.hotmart_client_secret
        self.base_url = "https://developers.hotmart.com"

    def _token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise HotmartError("Hotmart credentials not configured")
        raw = f"{self.client_id}:{self.client_secret}".encode()
        try:
            response = requests.post(
                "https://api-sec-vlc.hotmart.com/security/oauth/token",
                headers={"Authorization": "Basic " + base64.b64encode(raw).decode(), "Content-Type": "application/json"},
                params={"grant_type": "client_credentials"},
                timeout=20,
            )
            response.raise_for_status()
            token = response.json().get("access_token")
        except requests.RequestException as exc:
            raise HotmartError(f"Hotmart authentication failed: {exc}") from exc
        if not token:
            raise HotmartError("Hotmart authentication returned no access token")
        return str(token)

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        try:
            response = requests.get(
                self.base_url + path,
                headers={"Authorization": f"Bearer {self._token()}"},
                params=params,
                timeout=20,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise HotmartError(f"Hotmart request failed: {exc}") from exc

    async def list_products(self) -> list[dict[str, Any]]:
        data = self._get("/products/api/v1/products")
        return list(data.get("items") or data.get("products") or [])

    async def list_offers(self, ucode: str) -> list[dict[str, Any]]:
        data = self._get(f"/products/api/v1/products/{ucode}/offers")
        return list(data.get("items") or data.get("offers") or [])
