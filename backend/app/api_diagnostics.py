from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from .db.postgres import DatabaseError, PostgresStore
from .core.config import get_settings

router = APIRouter()
db = PostgresStore(get_settings())


class PersistenceTestCreate(BaseModel):
    purpose: str = Field(default="restart_recovery", pattern="^restart_recovery$")


@router.post("/api/v1/diagnostics/persistence-test", status_code=201)
async def create_persistence_test(
    request: PersistenceTestCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Create a harmless durable diagnostic record, without enqueueing business work."""
    key = (idempotency_key or "").strip()
    if not key or len(key) > 128:
        raise HTTPException(status_code=400, detail="Envie Idempotency-Key com 1 a 128 caracteres.")
    existing = await db.select(
        "hermes_persistence_tests",
        params={"idempotency_key": f"eq.{key}", "limit": "1"},
    )
    if existing:
        response.status_code = 200
        return {"created": False, "test": existing[0]}
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid4()),
        "idempotency_key": key,
        "purpose": request.purpose,
        "status": "pending",
        "execution_count": 0,
        "created_at": now,
        "updated_at": now,
        "operation": "diagnostic_noop",
    }
    try:
        created = await db.insert("hermes_persistence_tests", record)
        return {"created": True, "test": created}
    except Exception as exc:
        # A concurrent retry may win the unique idempotency index.
        if "duplicate" not in str(exc).lower() and "unique" not in str(exc).lower():
            raise
        existing = await db.select(
            "hermes_persistence_tests",
            params={"idempotency_key": f"eq.{key}", "limit": "1"},
        )
        if existing:
            response.status_code = 200
            return {"created": False, "test": existing[0]}
        raise


@router.get("/api/v1/diagnostics/persistence-test/{test_id}")
async def get_persistence_test(test_id: str) -> dict[str, Any]:
    rows = await db.select(
        "hermes_persistence_tests",
        params={"id": f"eq.{test_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Teste de persistência não encontrado.")
    return {"test": rows[0]}


@router.post("/api/v1/diagnostics/persistence-test/{test_id}/execute")
async def execute_persistence_test(test_id: str) -> dict[str, Any]:
    """Atomically record one no-op execution; retries cannot increment twice."""
    try:
        record, executed_now = await db.claim_persistence_test_execution(test_id)
    except DatabaseError as exc:
        if "não encontrado" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Teste de persistência não encontrado.") from exc
        raise
    return {
        "executed_now": executed_now,
        "already_executed": not executed_now,
        "test": record,
        "effect": "no-op",
    }
