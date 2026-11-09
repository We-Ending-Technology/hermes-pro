from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from ..core.config import Settings, get_supabase_server_key


class SupabaseError(RuntimeError):
    pass


class SupabaseREST:
    def __init__(self, settings: Settings) -> None:
        supabase_url = (settings.supabase_url or "").rstrip("/")
        self.secret_key = get_supabase_server_key(settings)
        self.bridge_secret = settings.supabase_bridge_secret or ""
        self.publishable_key = settings.supabase_publishable_key or ""
        if self.secret_key:
            self.base_url = f"{supabase_url}/rest/v1"
            self.headers = {
                "apikey": self.secret_key,
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json",
            }
        else:
            # Privileged DB access is isolated inside a Supabase Edge Function.
            # Render receives only a publishable key plus a separate bridge secret.
            self.base_url = f"{supabase_url}/functions/v1/hermes-db-bridge"
            self.headers = {
                "apikey": self.publishable_key,
                "x-hermes-bridge-key": self.bridge_secret,
                "Content-Type": "application/json",
            }

    def _ensure_configured(self) -> None:
        if not self.base_url.startswith("http"):
            raise SupabaseError("SUPABASE_URL is required")
        if not self.secret_key and (not self.bridge_secret or not self.publishable_key):
            raise SupabaseError(
                "Configure a Supabase server credential or the secured Edge Function bridge."
            )

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

    async def upsert(self, table: str, values: dict[str, Any], *, conflict: str) -> dict[str, Any]:
        result = await self.request(
            "POST",
            table,
            params={"on_conflict": conflict},
            json=values,
            prefer="resolution=merge-duplicates,return=representation",
        )
        if not result:
            raise SupabaseError(f"Supabase upsert {table} returned no row")
        return result[0]

    async def health(self) -> bool:
        try:
            await self.select("hermes_products", params={"select": "id", "limit": "1"})
            return True
        except Exception:
            return False
