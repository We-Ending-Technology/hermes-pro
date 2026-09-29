from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from ..ai_gateway.base import AIGateway
from ..core.config import Settings
from ..integrations.freelancer import build_freelancer_adapter
from .persistence import PersistentStore
from .storage import SupabaseStorage


class ExecutionError(RuntimeError):
    pass


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")[:80] or "delivery"


async def execute_service_job(
    *,
    job: dict[str, Any],
    store: PersistentStore,
    gateway: AIGateway,
    settings: Settings,
) -> dict[str, Any]:
    payload = dict(job.get("payload") or {})
    contract = payload.get("contract") or payload
    source = str(contract.get("source") or "")
    if source != "freelancer":
        raise ExecutionError(f"no real delivery adapter for source={source}")

    project_id = contract.get("project_id") or contract.get("external_id")
    bid_id = contract.get("bid_id")
    amount = float(contract.get("amount") or contract.get("budget") or 0)
    if not project_id or not bid_id or amount <= 0:
        raise ExecutionError("execution requires awarded project_id, bid_id and positive amount")

    title = str(contract.get("title") or "Freelancer service")
    description = str(contract.get("description") or "")
    prompt = (
        "Execute this freelance task as Hermes Pro. Produce the actual deliverable, not a plan. "
        "Use only the supplied requirements. Do not invent access, measurements, client facts or completed actions. "
        "If the task is research/report/content, return a complete professional deliverable in Markdown. "
        "If it is software/API work, return a complete implementation package in Markdown containing every required file "
        "with exact file paths and code blocks, plus tests and usage instructions. "
        "If a requirement cannot be completed without external credentials or unavailable files, mark that item explicitly "
        "as BLOCKED instead of pretending it was done. "
        f"TITLE: {title}\nREQUIREMENTS:\n{description[:12000]}"
    )
    result = await gateway.complete(prompt, system="You are Hermes Pro's execution worker. Deliver real work and never fabricate completion.")

    content = result.content.strip()
    if len(content) < 200:
        raise ExecutionError("generated deliverable is too short to be a credible submission")
    if "BLOCKED" in content[:1000] and contract.get("strict_execution", False):
        raise ExecutionError("execution contains blocked requirements under strict execution policy")

    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    slug = _slug(title)
    path = f"deliveries/{project_id}/{slug}-{digest[:12]}.md"
    storage = SupabaseStorage(settings, bucket="hermes-artifacts")
    url = await storage.upload(path, content.encode("utf-8"), "text/markdown")

    qa = {
        "passed": len(content) >= 200 and bool(url),
        "checks": {
            "non_empty": bool(content),
            "minimum_content": len(content) >= 200,
            "artifact_uploaded": bool(url),
            "sha256": digest,
        },
    }
    if not qa["passed"]:
        raise ExecutionError("delivery QA failed")

    adapter = build_freelancer_adapter(settings)
    request = await adapter.create_milestone_request(
        project_id=project_id,
        bid_id=bid_id,
        amount=amount,
        description=f"Entrega Hermes Pro: {title}\nArtefato: {url}\nSHA-256: {digest}",
    )

    delivery = {
        "status": "delivery_submitted",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "artifact_url": url,
        "artifact_path": path,
        "artifact_sha256": digest,
        "qa": qa,
        "provider": result.provider,
        "model": result.model,
        "milestone_request": request,
        "payment": {"status": "awaiting_client_release", "expected_amount": amount, "currency": contract.get("currency") or "USD"},
    }
    payload["delivery"] = delivery
    await store.update_job(str(job["id"]), "delivery_submitted", attempts=int(job.get("attempts", 0)), payload=payload)
    await store.append_event("freelancer", "DELIVERY_SUBMITTED", delivery, external_id=str(project_id), amount=amount, currency=contract.get("currency") or "USD")
    return delivery


async def sync_freelancer_contracts(*, store: PersistentStore, settings: Settings) -> dict[str, Any]:
    if not (settings.freelancer_enabled and settings.freelancer_access_token):
        return {"enabled": False, "awarded": 0, "queued": 0, "paid": 0}

    adapter = build_freelancer_adapter(settings)
    bidder_id = settings.freelancer_bidder_id
    if bidder_id is None:
        me = await adapter.self_user()
        user = (me.get("result") or {}).get("user") or me.get("user") or {}
        bidder_id = user.get("id")
    if not bidder_id:
        raise ExecutionError("could not determine Freelancer bidder id")

    awarded = await adapter.list_bids(bidder_id=int(bidder_id), award_status="awarded", limit=50)
    rows = (awarded.get("result") or {}).get("bids") or awarded.get("bids") or []
    queued = 0
    paid = 0

    for bid in rows:
        project = bid.get("project") or {}
        project_id = bid.get("project_id") or project.get("id")
        bid_id = bid.get("id")
        if not project_id or not bid_id:
            continue
        key = f"execution:freelancer:{project_id}:{bid_id}"
        existing = await store.create_job_if_absent(
            "service_execution",
            {
                "source": "freelancer",
                "project_id": project_id,
                "bid_id": bid_id,
                "title": project.get("title") or bid.get("project_title") or "Freelancer service",
                "description": project.get("description") or bid.get("description") or "",
                "amount": bid.get("amount") or project.get("budget", {}).get("maximum"),
                "currency": (project.get("currency") or {}).get("code") if isinstance(project.get("currency"), dict) else "USD",
                "contract": {"source": "freelancer", "project_id": project_id, "bid_id": bid_id},
            },
            key,
        )
        if existing.get("status") in {"pending", "retrying"}:
            queued += 1

        milestones = await adapter.list_project_milestones(project_id)
        mrows = (milestones.get("result") or {}).get("milestones") or milestones.get("milestones") or []
        for milestone in mrows:
            status = str(milestone.get("status") or "").lower().replace(" ", "_")
            if status in {"released", "cleared", "paid"}:
                amount = milestone.get("amount") or milestone.get("amount_released") or 0
                await store.append_event(
                    "freelancer",
                    "PAYMENT_RELEASED",
                    milestone,
                    external_id=f"{project_id}:{milestone.get('id')}",
                    amount=float(amount or 0),
                    currency="USD",
                )
                paid += 1

    return {"enabled": True, "awarded": len(rows), "queued": queued, "paid": paid}
