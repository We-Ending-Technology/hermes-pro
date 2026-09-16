from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

QUEUE_NAME = "hermes:jobs:product_generation"


class JobQueue:
    """Redis-first queue with a persistent Supabase polling fallback.

    Render does not provision Redis automatically. An empty/localhost Redis URL
    therefore must never become a production hard dependency.
    """

    def __init__(self, redis_url: str, db: Any | None = None) -> None:
        self.db = db
        self.redis_url = (redis_url or "").strip()
        self.redis: Redis | None = None
        if self.redis_url and not self.redis_url.startswith("redis://localhost") and not self.redis_url.startswith("redis://127.0.0.1"):
            self.redis = Redis.from_url(self.redis_url, decode_responses=True)

    @property
    def uses_redis(self) -> bool:
        return self.redis is not None

    async def enqueue(self, job_id: str) -> None:
        if self.redis is not None:
            try:
                await self.redis.lpush(QUEUE_NAME, json.dumps({"job_id": job_id}))
                return
            except Exception:
                # Persistent state remains the source of truth; dequeue fallback will recover it.
                pass
        # Supabase-backed mode needs no extra queue row: the persisted job status is the queue.
        return None

    async def dequeue(self, timeout: int = 10) -> str | None:
        if self.redis is not None:
            try:
                item = await self.redis.brpop(QUEUE_NAME, timeout=timeout)
                if item:
                    payload = json.loads(item[1])
                    return payload["job_id"]
            except Exception:
                pass
        if self.db is None:
            return None
        try:
            rows = await self.db.select(
                "hermes_jobs",
                params={"select": "id,status,attempts,max_attempts", "status": "in.(pending,retrying)", "order": "created_at.asc", "limit": "1"},
            )
        except Exception:
            return None
        return str(rows[0]["id"]) if rows else None

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
