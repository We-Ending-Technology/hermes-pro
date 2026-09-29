from __future__ import annotations

import hashlib
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


async def execute_service_job(*, job: dict[str, Any], store: PersistentStore, gateway: AIGateway, settings: Settings) -> dict[str, Any]:
    payload = dict(job.get("payload") or {})
    contract = payload.get("contract") or payload
    project_id = contract.get("project_id")
    bid_id = contract.get("bid_id")
    milestone_id = contract.get("milestone_id")
    amount = float(contract.get("amount") or 0)
    if contract.get("source") != "freelancer" or not project_id or not bid_id or not milestone_id or amount <= 0:
        raise ExecutionError("execution requires a Freelancer contract with a funded milestone")

    title = str(contract.get("title") or "Freelancer service")
    description = str(contract.get("description") or "")
    prompt = (
        "Execute the freelance task below and produce the actual deliverable. "
        "Do not invent facts, access, measurements or completed actions. "
        "For research/content/report tasks return a complete professional Markdown deliverable. "
        "For software/API tasks return complete files, code, tests and usage instructions. "
        "Explicitly mark unavailable inputs as BLOCKED.\n\n"
        f"TITLE: {title}\nREQUIREMENTS:\n{description[:12000]}"
    )
    result = await gateway.complete(prompt, system="You are Hermes Pro's execution worker. Produce real work, not a plan.")
    content = result.content.strip()
    if len(content) < 200:
        raise ExecutionError("deliverable failed minimum quality gate")

    digest = hashlib.sha256(content.encode()).hexdigest()
    path = f"deliveries/{project_id}/{_slug(title)}-{digest[:12]}.md"
    storage = SupabaseStorage(settings, bucket="hermes-artifacts")
    url = await storage.upload(path, content.encode(), "text/markdown")

    qa = {"passed": bool(url) and len(content) >= 200, "sha256": digest, "length": len(content)}
    if not qa["passed"]:
        raise ExecutionError("delivery QA failed")

    adapter = build_freelancer_adapter(settings)
    release_request = await adapter.request_milestone_release(milestone_id)
    delivery = {
        "status": "delivery_submitted",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "artifact_url": url,
        "artifact_path": path,
        "artifact_sha256": digest,
        "qa": qa,
        "provider": result.provider,
        "model": result.model,
        "milestone_id": milestone_id,
        "release_request": release_request,
        "payment": {"status": "awaiting_client_release", "expected_amount": amount, "currency": contract.get("currency") or "USD"},
    }
    payload["delivery"] = delivery
    await store.update_job(str(job["id"]), "delivery_submitted", attempts=int(job.get("attempts", 0)), payload=payload)
    await store.append_event("freelancer", "DELIVERY_SUBMITTED", delivery, external_id=f"{project_id}:{milestone_id}", amount=amount, currency=contract.get("currency") or "USD")
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
        milestones = await adapter.list_project_milestones(project_id)
        mrows = (milestones.get("result") or {}).get("milestones") or milestones.get("milestones") or []
        funded = None
        for milestone in mrows:
            status = str(milestone.get("status") or "").lower().replace(" ", "_")
            milestone_bid = milestone.get("bid_id") or (milestone.get("bid") or {}).get("id")
            if str(milestone_bid) == str(bid_id) and status in {"funded", "in_progress", "active"} and funded is None:
                funded = milestone
            if status in {"released", "cleared", "paid"}:
                amount_released = milestone.get("amount") or milestone.get("amount_released") or 0
                await store.append_event(
                    "freelancer", "PAYMENT_RELEASED", milestone,
                    external_id=f"{project_id}:{milestone.get('id')}",
                    amount=float(amount_released or 0), currency="USD",
                )
                paid += 1

        if not funded:
            continue
        key = f"execution:freelancer:{project_id}:{bid_id}:{funded.get('id')}"
        existing = await store.create_job_if_absent(
            "service_execution",
            {
                "source": "freelancer", "project_id": project_id, "bid_id": bid_id,
                "milestone_id": funded.get("id"),
                "title": project.get("title") or bid.get("project_title") or "Freelancer service",
                "description": project.get("description") or bid.get("description") or "",
                "amount": funded.get("amount") or bid.get("amount") or project.get("budget", {}).get("maximum"),
                "currency": "USD",
                "contract": {
                    "source": "freelancer", "project_id": project_id, "bid_id": bid_id,
                    "milestone_id": funded.get("id"),
                    "title": project.get("title") or bid.get("project_title") or "Freelancer service",
                    "description": project.get("description") or bid.get("description") or "",
                    "amount": funded.get("amount") or bid.get("amount") or project.get("budget", {}).get("maximum"),
                    "currency": "USD",
                },
            },
            key,
        )
        if existing.get("status") in {"pending", "retrying"}:
            queued += 1

    return {"enabled": True, "awarded": len(rows), "queued": queued, "paid": paid}
