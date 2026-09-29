from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from .core.config import get_settings
from .db.supabase import SupabaseREST
from .services.execution import execute_service_job, sync_freelancer_contracts
from .integrations.freelancer import build_freelancer_adapter
from .services.persistence import PersistentStore
from .ai_gateway.factory import build_ai_gateway

router = APIRouter(prefix="/api/v1/autonomy", tags=["autonomy"])
settings = get_settings()
db = SupabaseREST(settings)
store = PersistentStore(db)
gateway = build_ai_gateway(settings)


async def _require_scheduler(value: str | None) -> None:
    expected = await db.rpc("get_hermes_scheduler_secret")
    if not expected or value != expected:
        raise HTTPException(status_code=401, detail="invalid scheduler credential")


@router.post("/freelancer/sync")
async def freelancer_sync(x_hermes_scheduler: str | None = Header(default=None)) -> dict[str, Any]:
    await _require_scheduler(x_hermes_scheduler)
    return await sync_freelancer_contracts(store=store, settings=settings)



@router.post("/freelancer/apply/{job_id}")
async def freelancer_apply(
    job_id: str,
    x_hermes_scheduler: str | None = Header(default=None),
) -> dict[str, Any]:
    await _require_scheduler(x_hermes_scheduler)
    job = await store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    payload = dict(job.get("payload") or {})
    if payload.get("source") != "freelancer" or payload.get("application_automation_allowed") is not True:
        raise HTTPException(status_code=409, detail="automatic application is not enabled for this opportunity")
    proposal = payload.get("proposal") or {}
    price = ((proposal.get("suggested_price") or {}).get("recommended") if isinstance(proposal, dict) else None)
    project_id = payload.get("external_id") or payload.get("opportunity_id")
    if not project_id or not price:
        raise HTTPException(status_code=409, detail="missing Freelancer project id or suggested price")
    adapter = build_freelancer_adapter(settings)
    bid = await adapter.create_bid(
        project_id=project_id,
        amount=float(price),
        description=str(proposal.get("proposal_text") or "")[:5000],
        period=max(1, int(proposal.get("estimated_hours") or 8) // 8),
    )
    payload["submission"] = {"status": "submitted", "bid": bid}
    payload["status"] = "submitted"
    await store.update_job(job_id, "submitted", attempts=int(job.get("attempts", 0)), payload=payload, error_message=None)
    return {"ok": True, "job_id": job_id, "submission": bid}


@router.post("/jobs/{job_id}/execute")
async def execute_service(
    job_id: str,
    x_hermes_scheduler: str | None = Header(default=None),
) -> dict[str, Any]:
    await _require_scheduler(x_hermes_scheduler)
    job = await store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.get("job_type") != "service_execution":
        raise HTTPException(status_code=409, detail="job is not a service execution job")
    if job.get("status") in {"delivery_submitted", "paid", "cancelled"}:
        return {"ok": True, "status": job["status"], "job": job}

    attempts = int(job.get("attempts", 0)) + 1
    await store.update_job(job_id, "running", attempts=attempts, error_message=None)
    try:
        delivery = await execute_service_job(
            job=job,
            store=store,
            gateway=gateway,
            settings=settings,
        )
        return {"ok": True, "job_id": job_id, "delivery": delivery}
    except Exception as exc:
        await store.update_job(job_id, "failed", attempts=attempts, error_message=str(exc)[:1000])
        raise HTTPException(status_code=502, detail=str(exc)) from exc
