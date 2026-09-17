from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any


class WatchdogEngine:
    """Cheap, deterministic operational checks that wake autonomous recovery."""

    def __init__(self, store: Any, queue: Any | None = None, controls: Any | None = None, *, stale_after_seconds: int = 1800) -> None:
        self.store = store
        self.queue = queue
        self.controls = controls
        self.stale_after_seconds = stale_after_seconds

    @staticmethod
    def _parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    async def run_once(self, *, now: str | None = None) -> dict[str, int]:
        current = self._parse(now) if now else datetime.now(timezone.utc)
        jobs = await self.store.list_jobs()
        detected = 0
        recovered = 0
        fingerprints: list[str] = []
        for job in jobs:
            if job.get("status") not in {"running", "retrying", "queued"}:
                continue
            updated = job.get("updated_at") or job.get("created_at")
            if not updated:
                continue
            age = (current - self._parse(updated)).total_seconds()
            if age <= self.stale_after_seconds:
                continue
            fingerprint = hashlib.sha256(f"stalled-job:{job['id']}".encode()).hexdigest()
            await self.store.upsert_incident(fingerprint, {
                "kind": "stalled_job",
                "severity": "warning",
                "status": "open",
                "summary": f"Job {job['id']} has been inactive for {int(age)} seconds",
                "evidence": {"job_id": str(job["id"]), "age_seconds": int(age)},
                "last_seen_at": current.isoformat(),
            })
            fingerprints.append(fingerprint)
            detected += 1
            attempts = int(job.get("attempts") or 0)
            max_attempts = int(job.get("max_attempts") or 3)
            allowed = self.controls.is_allowed("retry_job") if self.controls else None
            if self.queue and self.controls and allowed and allowed.allowed and attempts < max_attempts:
                await self.store.update_job(str(job["id"]), "retrying", attempts=attempts + 1, error_message="watchdog: stale job recovered")
                await self.queue.enqueue(str(job["id"]))
                recovered += 1
        return {"checks": 1, "incidents": detected, "recovered": recovered, "fingerprints": len(set(fingerprints))}