from __future__ import annotations

import json
from redis.asyncio import Redis

QUEUE_NAME = "hermes:jobs"

class JobQueue:
    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    async def enqueue(self, job_id: str) -> None:
        await self.redis.lpush(QUEUE_NAME, json.dumps({"job_id": job_id}))

    async def enqueue_agent(self, job_id: str) -> None:
        await self.redis.lpush("hermes:agent_jobs", json.dumps({"job_id": job_id}))

    async def dequeue_agent(self, timeout: int = 1) -> str | None:
        item = await self.redis.brpop("hermes:agent_jobs", timeout=timeout)
        if not item:
            return None
        return json.loads(item[1])["job_id"]

    async def dequeue(self, timeout: int = 10) -> str | None:
        item = await self.redis.brpop(QUEUE_NAME, timeout=timeout)
        if not item:
            return None
        return json.loads(item[1])["job_id"]

    async def close(self) -> None:
        await self.redis.aclose()
