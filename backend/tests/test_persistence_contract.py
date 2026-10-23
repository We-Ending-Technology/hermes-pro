from __future__ import annotations

import pytest

from backend.app.services.persistence import PersistentStore


class FakePostgresStore:
    def __init__(self) -> None:
        self.inserted: list[tuple[str, dict]] = []
        self.updated: list[tuple[str, dict, dict]] = []

    async def select(self, table: str, *, params=None):
        return []

    async def insert(self, table: str, values: dict):
        record = {**values, "id": f"id-{len(self.inserted) + 1}"}
        self.inserted.append((table, record))
        return record

    async def update(self, table: str, values: dict, *, where: dict[str, str]):
        self.updated.append((table, values, where))
        return {"id": where["id"].removeprefix("eq."), **values}


@pytest.mark.asyncio
async def test_create_product_and_job_uses_postgres_update_contract():
    db = FakePostgresStore()
    store = PersistentStore(db)

    product, job = await store.create_product_and_job(
        "Relatório automatizado",
        {"source": "test"},
        "test-idempotency-key",
    )

    assert product["job_id"] == job["id"]
    assert job["payload"]["product_id"] == product["id"]
    assert db.updated == [
        (
            "hermes_products",
            {"job_id": job["id"], "updated_at": product["updated_at"]},
            {"id": f"eq.{product['id']}"},
        )
    ]
