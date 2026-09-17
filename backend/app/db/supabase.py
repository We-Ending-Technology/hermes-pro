from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
import logging

import httpx

from ..core.config import Settings

logger = logging.getLogger("hermes.supabase")


class SupabaseError(RuntimeError):
    pass


class SupabaseREST:
    def __init__(self, settings: Settings) -> None:
        self.project_url = (settings.supabase_url or "").rstrip("/")
        self.base_url = self.project_url + "/rest/v1"
        self.storage_url = self.project_url + "/storage/v1"
        self.secret_key = settings.supabase_secret_key
        self.internal_api_key = settings.supabase_internal_api_key
        self.headers = {
            "apikey": settings.supabase_secret_key or "",
            "Authorization": f"Bearer {settings.supabase_secret_key or ''}",
            "Content-Type": "application/json",
        }
        if self.internal_api_key:
            self.headers["x-hermes-internal-key"] = self.internal_api_key

    def _ensure_configured(self) -> None:
        if not self.secret_key or not self.project_url.startswith("http"):
            raise SupabaseError("SUPABASE_URL and a Supabase service key are required")

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, (UUID, datetime)):
            return str(value)
        return value

    async def request(self, method: str, table: str, *, params: dict[str, str] | None = None, json: Any = None, prefer: str | None = None) -> Any:
        self._ensure_configured()
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(method, f"{self.base_url}/{table}", headers=headers, params=params, json=json)
        if response.is_error:
            detail = response.text[:500]
            logger.error("Supabase request failed: method=%s table=%s status=%s detail=%s", method, table, response.status_code, detail)
            raise SupabaseError(f"Supabase {method} {table} failed: {response.status_code} {detail}")
        if not response.content:
            return None
        return response.json()

    async def select(self, table: str, *, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        result = await self.request("GET", table, params=params or {})
        return result or []

    async def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        result = await self.request("POST", table, json=values, prefer="return=representation")
        if not result:
            raise SupabaseError(f"Supabase insert {table} returned no row")
        return result[0]

    async def update(self, table: str, values: dict[str, Any], *, where: dict[str, str]) -> dict[str, Any]:
        result = await self.request("PATCH", table, params=where, json=values, prefer="return=representation")
        if not result:
            raise SupabaseError(f"Supabase update {table} matched no rows")
        return result[0]

    async def upload_storage(self, bucket: str, path: str, data: bytes, content_type: str) -> dict[str, Any]:
        self._ensure_configured()
        headers = {
            "apikey": self.secret_key or "",
            "Authorization": f"Bearer {self.secret_key or ''}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        if self.internal_api_key:
            headers["x-hermes-internal-key"] = self.internal_api_key
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.storage_url}/object/{bucket}/{path}", headers=headers, content=data)
        if response.is_error:
            raise SupabaseError(f"Supabase storage upload failed: {response.status_code} {response.text[:500]}")
        return response.json() if response.content else {"path": path}

    async def create_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        self._ensure_configured()
        headers = {"apikey": self.secret_key or "", "Authorization": f"Bearer {self.secret_key or ''}", "Content-Type": "application/json"}
        if self.internal_api_key:
            headers["x-hermes-internal-key"] = self.internal_api_key
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.storage_url}/object/sign/{bucket}/{path}", headers=headers, json={"expiresIn": expires_in})
        if response.is_error:
            raise SupabaseError(f"Supabase signed URL failed: {response.status_code} {response.text[:500]}")
        payload = response.json()
        signed = payload.get("signedURL") or payload.get("signedUrl")
        if not signed:
            raise SupabaseError("Supabase signed URL response did not include signedURL")
        if signed.startswith("http"):
            return signed
        return f"{self.storage_url}{signed}"

    async def health(self) -> bool:
        try:
            await self.select("hermes_products", params={"select": "id", "limit": "1"})
            return True
        except Exception:
            return False
