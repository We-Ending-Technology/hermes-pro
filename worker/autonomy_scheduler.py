from __future__ import annotations

import time
from datetime import datetime, timezone

from backend.app.core.config import Settings
from backend.app.services.persistence import PersistentStore


async def autonomy_tick(settings: Settings, store: PersistentStore, queue) -> None:
    if not settings.autonomy_enabled or not settings.openai_api_key:
        return
    jobs = await store.list_jobs()
    active = [
        j for j in jobs
        if j.get("job_type") == "agent_run" and j.get("status") in {"pending", "running", "retrying"}
    ]
    if active:
        return
    now = datetime.now(timezone.utc).isoformat()
    job = await store.create_agent_job(
        "Run the Hermes autonomous operations check. Inspect pending product/jobs state, "
        "identify failures or useful next actions, and report what Hermes should do next. "
        "Do not perform irreversible external actions.",
        source="scheduler",
        now=now,
    )
    await queue.enqueue_agent(str(job["id"]))
