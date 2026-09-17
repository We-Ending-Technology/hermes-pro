from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..db.supabase import SupabaseREST
from ..models.jobs import JobStatus
from ..product_factory import PIPELINE_STAGES


class PersistentStore:
    def __init__(self, db: SupabaseREST) -> None:
        self.db = db

    async def create_product_and_job(self, topic: str, metadata: dict[str, Any], idempotency_key: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        if idempotency_key:
            existing = await self.db.select("hermes_products", params={"select": "*", "idempotency_key": f"eq.{idempotency_key}", "limit": "1"})
            if existing:
                jobs = await self.db.select("hermes_jobs", params={"select": "*", "payload->>product_id": f"eq.{existing[0]['id']}", "limit": "1"})
                if jobs:
                    return existing[0], jobs[0]
        now = datetime.now(timezone.utc).isoformat()
        product = await self.db.insert("hermes_products", {
            "topic": topic.strip(), "status": "queued", "current_stage": PIPELINE_STAGES[0],
            "metadata": metadata or {}, "idempotency_key": idempotency_key, "created_at": now, "updated_at": now,
        })
        job = await self.db.insert("hermes_jobs", {
            "job_type": "product_generation", "status": JobStatus.PENDING.value,
            "attempts": 0, "max_attempts": 3,
            "payload": {"product_id": product["id"], "topic": product["topic"]},
            "idempotency_key": idempotency_key, "created_at": now, "updated_at": now,
        })
        product = await self.db.update("hermes_products", {"job_id": job["id"], "updated_at": now}, where={"id": f"eq.{product['id']}"})
        return product, job

    async def get_product(self, product_id: str) -> dict[str, Any] | None:
        rows = await self.db.select("hermes_products", params={"select": "*", "id": f"eq.{product_id}", "limit": "1"})
        return rows[0] if rows else None

    async def list_products(self) -> list[dict[str, Any]]:
        return await self.db.select("hermes_products", params={"select": "*", "order": "created_at.desc"})

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        rows = await self.db.select("hermes_jobs", params={"select": "*", "id": f"eq.{job_id}", "limit": "1"})
        return rows[0] if rows else None

    async def list_jobs(self) -> list[dict[str, Any]]:
        return await self.db.select("hermes_jobs", params={"select": "*", "order": "created_at.desc"})

    async def update_job(self, job_id: str, status: str, *, attempts: int | None = None, error_message: str | None = None) -> dict[str, Any]:
        values: dict[str, Any] = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat(), "error_message": error_message}
        if attempts is not None:
            values["attempts"] = attempts
        return await self.db.update("hermes_jobs", values, where={"id": f"eq.{job_id}"})

    async def update_product(self, product_id: str, *, status: str | None = None, current_stage: str | None = None, title: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        values: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if status is not None: values["status"] = status
        if current_stage is not None: values["current_stage"] = current_stage
        if title is not None: values["title"] = title
        if metadata is not None: values["metadata"] = metadata
        return await self.db.update("hermes_products", values, where={"id": f"eq.{product_id}"})

    async def upsert_incident(self, fingerprint: str, values: dict[str, Any]) -> dict[str, Any]:
        existing = await self.db.select("hermes_incidents", params={"select": "*", "fingerprint": f"eq.{fingerprint}", "limit": "1"})
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            row = existing[0]
            return await self.db.update("hermes_incidents", {
                **values,
                "last_seen_at": now,
                "updated_at": now,
                "attempts": int(row.get("attempts") or 0) + 1,
            }, where={"id": f"eq.{row['id']}"})
        return await self.db.insert("hermes_incidents", {"fingerprint": fingerprint, **values, "attempts": 1, "created_at": now, "updated_at": now})

    async def list_incidents(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self.db.select("hermes_incidents", params={"select": "*", "order": "last_seen_at.desc", "limit": str(limit)})

    async def record_watchdog_check(self, check_name: str, result: dict[str, Any], *, status: str = "ok") -> dict[str, Any]:
        existing = await self.db.select("hermes_watchdog_checks", params={"select": "*", "check_name": f"eq.{check_name}", "limit": "1"})
        now = datetime.now(timezone.utc).isoformat()
        values = {"last_run_at": now, "last_status": status, "last_result": result, "updated_at": now}
        if existing:
            row = existing[0]
            values["run_count"] = int(row.get("run_count") or 0) + 1
            if status != "ok": values["failure_count"] = int(row.get("failure_count") or 0) + 1
            return await self.db.update("hermes_watchdog_checks", values, where={"id": f"eq.{row['id']}"})
        values.update({"check_name": check_name, "run_count": 1, "failure_count": 0})
        return await self.db.insert("hermes_watchdog_checks", values)

    async def append_event(self, provider: str, event_type: str, payload: dict[str, Any], external_id: str | None = None, amount: float | None = None, currency: str | None = None) -> dict[str, Any]:
        return await self.db.insert("hermes_sales_events", {
            "provider": provider, "event_type": event_type, "external_id": external_id,
            "amount": amount, "currency": currency, "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(), "created_at": datetime.now(timezone.utc).isoformat(),
        })