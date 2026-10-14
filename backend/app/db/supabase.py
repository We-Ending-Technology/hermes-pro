from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
import base64
import json

import httpx

from ..core.config import Settings


class SupabaseError(RuntimeError):
    pass


class SupabaseREST:
    def __init__(self, settings: Settings) -> None:
        self.base_url = (settings.supabase_url or "").rstrip("/") + "/rest/v1"
        # Prefer an explicitly named server-role key, but accept the newer sb_secret_* key.
        # Never silently use a publishable/anon key for server-side writes.
        raw_candidates = [
            settings.supabase_service_role_key,
            settings.supabase_service_key,
            settings.supabase_secret_key,
        ]
        # Normalize common copy/paste whitespace or quote wrappers before checking
        # the credential type; never promote anon/publishable keys to server keys.
        candidates = [
            str(key).strip().strip('"').strip("'").strip() if key else None
            for key in raw_candidates
        ]
        self.secret_key = next((key for key in candidates if key and (
            key.startswith("sb_secret_") or self._jwt_role(key) == "service_role"
        )), None)
        # Safe diagnostic only: never log the secret value.
        key = self.secret_key or ""
        key_kind = "sb_secret" if key.startswith("sb_secret_") else ("legacy_jwt" if key.startswith("eyJ") else ("missing" if not key else "other"))
        import logging
        logging.getLogger("hermes.api.supabase").info("Supabase credential kind=%s", key_kind)
        self.headers = {
            "apikey": self.secret_key or "",
            "Content-Type": "application/json",
        }
        # Supabase's newer sb_secret_* API keys are opaque API keys, not JWTs.
        # They must be sent via apikey only; using them as a Bearer token can
        # cause PostgREST to evaluate requests as anon and enforce RLS.
        # Legacy service_role/anon keys are JWTs and still need Authorization.
        if self.secret_key and self.secret_key.startswith("eyJ"):
            self.headers["Authorization"] = f"Bearer {self.secret_key}"

    @staticmethod
    def _jwt_role(key: str) -> str | None:
        try:
            parts = key.split(".")
            if len(parts) != 3:
                return None
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
            role = json.loads(decoded.decode("utf-8")).get("role")
            return role if isinstance(role, str) else None
        except Exception:
            return None

    def _ensure_configured(self) -> None:
        if not self.base_url.startswith("http"):
            raise SupabaseError("SUPABASE_URL is required")
        if not self.secret_key:
            raise SupabaseError(
                "A server-side Supabase key is required: use SUPABASE_SERVICE_ROLE_KEY "
                "or a Supabase sb_secret_* key. Publishable/anon keys cannot authorize worker writes."
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
        result = await self.request("POST", table, params={"on_conflict": conflict}, json=values, prefer="resolution=merge-duplicates,return=representation")
        if not result:
            raise SupabaseError(f"Supabase upsert {table} returned no row")
        return result[0]

    async def rpc(self, function: str, payload: dict[str, Any] | None = None) -> Any:
        self._ensure_configured()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/rpc/{function}",
                headers=self.headers,
                json=payload or {},
            )
        if response.is_error:
            raise SupabaseError(f"Supabase RPC {function} failed: {response.status_code} {response.text[:500]}")
        if not response.content:
            return None
        return response.json()

    async def health(self) -> bool:
        try:
            await self.select("hermes_products", params={"select": "id", "limit": "1"})
            return True
        except Exception:
            return False
