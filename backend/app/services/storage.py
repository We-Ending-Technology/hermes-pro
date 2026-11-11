from __future__ import annotations

import httpx

from ..core.config import Settings, get_supabase_server_key


class StorageError(RuntimeError):
    pass


class SupabaseStorage:
    def __init__(self, settings: Settings, bucket: str = "hermes-artifacts") -> None:
        self.base = (settings.supabase_url or "").rstrip("/")
        self.secret_key = get_supabase_server_key(settings)
        self.bridge_secret = settings.supabase_bridge_secret or ""
        self.publishable_key = settings.supabase_publishable_key or ""
        self.bucket = bucket
        if self.secret_key:
            self.storage_base = f"{self.base}/storage/v1"
        else:
            self.storage_base = f"{self.base}/functions/v1/hermes-db-bridge/storage"

    def _headers(self) -> dict[str, str]:
        if self.secret_key:
            headers = {"apikey": self.secret_key}
            # New sb_secret_ keys are opaque API keys, not JWTs.
            if self.secret_key.startswith("eyJ"):
                headers["Authorization"] = f"Bearer {self.secret_key}"
            return headers
        return {
            "apikey": self.publishable_key,
            "x-hermes-bridge-key": self.bridge_secret,
        }

    def _ensure_configured(self) -> None:
        if not self.base.startswith("http"):
            raise StorageError("SUPABASE_URL is required")
        if not self.secret_key and (not self.publishable_key or not self.bridge_secret):
            raise StorageError("Configure a Supabase server credential or the secured Edge Function bridge")

    async def ensure_bucket(self) -> None:
        self._ensure_configured()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.storage_base}/bucket",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"id": self.bucket, "name": self.bucket, "public": False},
            )

            # Supabase Storage can return HTTP 400 with an embedded 409
            # BucketAlreadyExists payload. Treat that as an existing bucket,
            # then explicitly enforce private visibility with the update API.
            duplicate = response.status_code == 409
            if response.status_code == 400:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                duplicate = (
                    payload.get("code") == "BucketAlreadyExists"
                    or (
                        str(payload.get("statusCode")) == "409"
                        and payload.get("error") == "Duplicate"
                    )
                )

            if duplicate:
                response = await client.put(
                    f"{self.storage_base}/bucket/{self.bucket}",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"public": False},
                )

            if response.status_code not in {200, 201}:
                raise StorageError(f"Private storage bucket setup failed: {response.status_code} {response.text[:300]}")

    def _absolute_signed_url(self, signed_path: str) -> str:
        if signed_path.startswith("http"):
            return signed_path
        if signed_path.startswith("/storage/v1/"):
            return f"{self.base}{signed_path}"
        return f"{self.base}/storage/v1{signed_path if signed_path.startswith('/') else '/' + signed_path}"

    async def create_signed_url(self, path: str, expires_in: int = 604800) -> str:
        self._ensure_configured()
        async with httpx.AsyncClient(timeout=30) as client:
            signed = await client.post(
                f"{self.storage_base}/object/sign/{self.bucket}/{path}",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"expiresIn": max(60, min(int(expires_in), 31536000))},
            )
            if signed.is_error:
                raise StorageError(f"Private artifact link creation failed: {signed.status_code} {signed.text[:500]}")
            signed_path = signed.json().get("signedURL") or signed.json().get("signedUrl")
            if not signed_path:
                raise StorageError("Supabase did not return a signed artifact URL")
        return self._absolute_signed_url(signed_path)

    async def upload(self, path: str, content: bytes, content_type: str) -> str:
        await self.ensure_bucket()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.storage_base}/object/{self.bucket}/{path}",
                headers={**self._headers(), "Content-Type": content_type, "x-upsert": "true"},
                content=content,
            )
            if response.is_error:
                raise StorageError(f"Storage upload failed: {response.status_code} {response.text[:500]}")
        return await self.create_signed_url(path, expires_in=604800)
