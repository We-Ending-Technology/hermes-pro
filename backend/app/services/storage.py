from __future__ import annotations

import httpx

from ..core.config import Settings


class StorageError(RuntimeError):
    pass


class SupabaseStorage:
    def __init__(self, settings: Settings, bucket: str = "hermes-artifacts") -> None:
        self.base = (settings.supabase_url or "").rstrip("/")
        self.key = settings.supabase_secret_key or ""
        self.bucket = bucket

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}"}

    async def ensure_bucket(self) -> None:
        if not self.base or not self.key:
            raise StorageError("Supabase storage is not configured")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base}/storage/v1/bucket",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"id": self.bucket, "name": self.bucket, "public": True},
            )
            if response.status_code not in {200, 201, 409}:
                raise StorageError(f"Storage bucket setup failed: {response.status_code} {response.text[:300]}")

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
        return f"{self.base}/storage/v1/object/public/{self.bucket}/{path}"
