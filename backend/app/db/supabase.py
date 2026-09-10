from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from ..core.config import Settings


class SupabaseError(RuntimeError):
    pass


class SupabaseREST:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url or not settings.supabase_secret_key:
            raise SupabaseError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
        self.base_url = settings.supabase_url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": settings.supabase_secret_key,
            "Authorization": f"Bearer {settings.supabase_secret_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, (UUID, datetime)):
            return str(value)
        return value

    async def request(self, method: str, table: str, *, params: dict[str, str] | None = None,
                     json: Any = None, prefer: str | None = None) -> Any:
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method, f"{self.base_url}/{table}", headers=headers, params=params, json=json
            )
        if response.is_error:
            raise SupabaseError(f"Supabase {method} {table} failed: {response.status_code} {response.text[:500]}")
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

    async def health(self) -> bool:
        try:
            await self.select("hermes_products", params={"select": "id", "limit": "1"})
            return True
        except Exception:
            return False
