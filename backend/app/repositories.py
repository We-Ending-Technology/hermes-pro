from typing import Any
import httpx
from .core.config import Settings

class SupabaseRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def insert(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.supabase_configured:
            raise RuntimeError("Supabase is not configured")
        url = f"{self.settings.supabase_url}/rest/v1/{table}"
        headers = {"apikey": self.settings.supabase_service_role_key, "Authorization": f"Bearer {self.settings.supabase_service_role_key}", "Prefer": "return=representation"}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, headers=headers, json=row)
            response.raise_for_status()
            return response.json()[0]

class ProductStore:
    def __init__(self) -> None:
        self.products: list[dict[str, Any]] = []

    async def create(self, product: dict[str, Any]) -> dict[str, Any]:
        self.products.append(product)
        return product

    async def list(self) -> list[dict[str, Any]]:
        return list(self.products)
