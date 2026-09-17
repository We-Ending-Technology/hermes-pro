from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any


class WatchdogEngine:
    """Cheap, deterministic operational checks that wake autonomous recovery."""

    def __init__(self, store: Any, *, stale_after_seconds: int = 1800) -> None:
        self.store = store
        self.stale_after_seconds = stale_after_seconds

    @staticmethod
    def _parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    async def run_once(self, *, now: str | None = None) -> dict[str, int]:
        current = self._parse(now) if now else datetime.now(timezone.utc)
        jobs = await self.store.list_jobs()
        detected = 0
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
        return {"checks": 1, "incidents": detected, "fingerprints": len(set(fingerprints))}
