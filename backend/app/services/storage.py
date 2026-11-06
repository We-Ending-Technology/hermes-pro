from __future__ import annotations

import httpx

from ..core.config import Settings, get_supabase_server_key


class StorageError(RuntimeError):
    pass


class SupabaseStorage:
    def __init__(self, settings: Settings, bucket: str = "hermes-artifacts") -> None:
        self.base = (settings.supabase_url or "").rstrip("/")
        self.key = get_supabase_server_key(settings) or ""
        self.bucket = bucket

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}"}

    async def ensure_bucket(self) -> None:
        if not self.base or not self.key:
            raise StorageError("Supabase server credential is not configured")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base}/storage/v1/bucket",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"id": self.bucket, "name": self.bucket, "public": False},
            )
            if response.status_code == 409:
                response = await client.put(
                    f"{self.base}/storage/v1/bucket/{self.bucket}",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={"public": False},
                )
            if response.status_code not in {200, 201}:
                raise StorageError(f"Private storage bucket setup failed: {response.status_code} {response.text[:300]}")

    async def upload(self, path: str, content: bytes, content_type: str) -> str:
        await self.ensure_bucket()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base}/storage/v1/object/{self.bucket}/{path}",
                headers={**self._headers(), "Content-Type": content_type, "x-upsert": "true"},
                content=content,
            )
            if response.is_error:
                raise StorageError(f"Storage upload failed: {response.status_code} {response.text[:500]}")
            signed = await client.post(
                f"{self.base}/storage/v1/object/sign/{self.bucket}/{path}",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"expiresIn": 604800},
            )
            if signed.is_error:
                raise StorageError(f"Private artifact link creation failed: {signed.status_code} {signed.text[:500]}")
            signed_path = signed.json().get("signedURL") or signed.json().get("signedUrl")
            if not signed_path:
                raise StorageError("Supabase did not return a signed artifact URL")
        if signed_path.startswith("http"):
            return signed_path
        if signed_path.startswith("/storage/v1/"):
            return f"{self.base}{signed_path}"
        return f"{self.base}/storage/v1{signed_path if signed_path.startswith('/') else '/' + signed_path}"
