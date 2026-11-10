from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..db.supabase import SupabaseREST
from ..models.jobs import Job, JobStatus
from ..product_factory import PIPELINE_STAGES


class PersistentStore:
    def __init__(self, db: SupabaseREST) -> None:
        self.db = db

    async def create_product_and_job(self, topic: str, metadata: dict[str, Any], idempotency_key: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        product = None
        if idempotency_key:
            existing = await self.db.select(
                "hermes_products",
                params={"select": "*", "idempotency_key": f"eq.{idempotency_key}", "limit": "1"},
            )
            product = existing[0] if existing else None
            jobs = await self.db.select(
                "hermes_jobs",
                params={"select": "*", "idempotency_key": f"eq.{idempotency_key}", "limit": "1"},
            )
            if product and jobs:
                return product, jobs[0]

        now = datetime.now(timezone.utc).isoformat()
        if product is None:
            product = await self.db.insert("hermes_products", {
                "topic": topic.strip(),
                "status": "queued",
                "current_stage": PIPELINE_STAGES[0],
                "metadata": metadata or {},
                "idempotency_key": idempotency_key,
                "created_at": now,
                "updated_at": now,
            })

        job_values = {
            "job_type": "product_generation",
            "status": JobStatus.PENDING.value,
            "attempts": 0,
            "max_attempts": 3,
            "payload": {"product_id": product["id"], "topic": product["topic"]},
            "idempotency_key": idempotency_key,
            "created_at": now,
            "updated_at": now,
        }
        job = await self.db.insert("hermes_jobs", job_values)
        product = await self.db.update(
            "hermes_products",
            {"job_id": job["id"], "updated_at": now},
            where={"id": f"eq.{product['id']}"},
        )
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

    async def list_recoverable_jobs(self, stale_before: datetime) -> list[dict[str, Any]]:
        cutoff = stale_before.astimezone(timezone.utc).isoformat()
        return await self.db.select(
            "hermes_jobs",
            params={
                "select": "*",
                "or": f"(status.eq.pending,status.eq.retrying,and(status.eq.running,updated_at.lt.{cutoff}))",
                "order": "created_at.asc",
            },
        )

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

    async def create_agent_job(
        self,
        instruction: str,
        source: str,
        now: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if idempotency_key:
            existing = await self.db.select(
                "hermes_jobs",
                params={"select": "*", "idempotency_key": "eq." + idempotency_key, "limit": "1"},
            )
            if existing:
                row = existing[0]
                runs = await self.db.select(
                    "hermes_agent_runs",
                    params={"select": "id", "id": "eq." + str(row["id"]), "limit": "1"},
                )
                if not runs:
                    await self.db.insert("hermes_agent_runs", {
                        "id": row["id"],
                        "agent": "Hermes Chefe",
                        "status": row["status"],
                        "input": row.get("payload") or {},
                        "output": {},
                        "created_at": row.get("created_at") or now,
                    })
                return row

        row = await self.db.insert("hermes_jobs", {
            "job_type": "agent_run",
            "status": "pending",
            "attempts": 0,
            "max_attempts": 3,
            "payload": {"instruction": instruction, "source": source},
            "idempotency_key": idempotency_key,
            "created_at": now,
            "updated_at": now,
        })
        try:
            await self.db.insert("hermes_agent_runs", {
                "id": row["id"],
                "agent": "Hermes Chefe",
                "status": "pending",
                "input": {"instruction": instruction, "source": source},
                "output": {},
                "created_at": now,
            })
        except Exception as exc:
            try:
                await self.update_job(
                    str(row["id"]),
                    "failed",
                    error_message="agent run persistence failed: " + str(exc)[:700],
                )
            finally:
                raise
        return row

    async def list_agent_runs(self) -> list[dict[str, Any]]:
        runs = await self.db.select(
            "hermes_agent_runs",
            params={"select": "*", "order": "created_at.desc", "limit": "50"},
        )
        if not runs:
            return []
        ids = [str(run["id"]) for run in runs]
        jobs = await self.db.select(
            "hermes_jobs",
            params={"select": "id,status,attempts,max_attempts,error_message,updated_at", "id": "in.(" + ",".join(ids) + ")"},
        )
        by_id = {str(job["id"]): job for job in jobs}
        for run in runs:
            job = by_id.get(str(run["id"]), {})
            run["job_status"] = job.get("status", run.get("status"))
            run["attempts"] = job.get("attempts", 0)
            run["max_attempts"] = job.get("max_attempts", 3)
            run["job_error"] = job.get("error_message")
            run["updated_at"] = job.get("updated_at", run.get("completed_at") or run.get("created_at"))
        return runs

    async def record_worker_health(self, status: str, message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.upsert(
            "hermes_system_health",
            {"component": "worker", "status": status, "message": message[:500], "checked_at": now},
            conflict="component",
        )

    async def append_event(self, provider: str, event_type: str, payload: dict[str, Any], external_id: str | None = None, amount: float | None = None, currency: str | None = None) -> dict[str, Any]:
        return await self.db.insert("hermes_sales_events", {
            "provider": provider, "event_type": event_type, "external_id": external_id,
            "amount": amount, "currency": currency, "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(), "created_at": datetime.now(timezone.utc).isoformat(),
        })
