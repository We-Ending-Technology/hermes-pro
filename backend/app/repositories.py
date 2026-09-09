from typing import Any
import httpx
from .core.config import Settings

class SupabaseRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        key = self.settings.supabase_key
        return {"apikey": key or "", "Authorization": f"Bearer {key or ''}", "Content-Type": "application/json", "Prefer": "return=representation"}

    async def request(self, method: str, table: str, *, params: dict[str, str] | None = None, payload: dict | None = None) -> list[dict[str, Any]]:
        if not self.settings.supabase_configured:
            raise RuntimeError("Supabase is not configured")
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(method, f"{self.settings.supabase_url}/rest/v1/{table}", headers=self._headers(), params=params, json=payload)
            response.raise_for_status()
            return response.json() if response.content else []

    async def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        return (await self.request("POST", table, payload=row))[0]

    async def update(self, table: str, filters: dict[str, str], row: dict[str, Any]) -> list[dict[str, Any]]:
        return await self.request("PATCH", table, params={key: f"eq.{value}" for key, value in filters.items()}, payload=row)

    async def list(self, table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        return await self.request("GET", table, params=params or {"select": "*"})

class PersistentJobStore:
    def __init__(self, repository: SupabaseRepository) -> None:
        self.repository = repository

    async def create(self, job_type: str, payload: dict) -> dict:
        return await self.repository.insert("jobs", {"job_type": job_type, "payload": payload, "status": "pending"})

    async def update(self, job_id: str, **changes: Any) -> dict:
        rows = await self.repository.update("jobs", {"id": job_id}, changes)
        return rows[0] if rows else {"id": job_id, **changes}

    async def pending(self) -> list[dict]:
        return await self.repository.list("jobs", {"select": "*", "status": "in.(pending,retrying)", "order": "created_at.asc"})

class PersistentProductStore:
    def __init__(self, repository: SupabaseRepository) -> None:
        self.repository = repository

    async def create(self, product: dict[str, Any]) -> dict:
        return await self.repository.insert("products", {"topic": product["topic"], "quality_score": product["quality_score"], "status": "draft", "document_path": product.get("document_path")})

    async def list(self) -> list[dict]:
        return await self.repository.list("products", {"select": "*", "order": "created_at.desc"})

class ProductStore:
    """Explicit development-only store used when Supabase is not configured."""
    def __init__(self) -> None:
        self.products: list[dict[str, Any]] = []
    async def create(self, product: dict[str, Any]) -> dict[str, Any]:
        self.products.append(product); return product
    async def list(self) -> list[dict[str, Any]]: return list(self.products)
