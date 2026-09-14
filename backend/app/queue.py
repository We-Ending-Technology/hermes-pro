from __future__ import annotations

import asyncio
import json

from redis.asyncio import Redis


QUEUE_NAME = "hermes:jobs:product_generation"


class JobQueue:
    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.local_queue: asyncio.Queue[str] = asyncio.Queue()
        self.redis_available = True

    async def enqueue(self, job_id: str) -> None:
        payload = json.dumps({"job_id": job_id})
        try:
            await self.redis.lpush(QUEUE_NAME, payload)
            self.redis_available = True
            return
        except Exception:
            self.redis_available = False
            await self.local_queue.put(job_id)

    async def dequeue(self, timeout: int = 10) -> str | None:
        if not self.redis_available:
            try:
                return await asyncio.wait_for(self.local_queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                try:
                    await self.redis.ping()
                    self.redis_available = True
                except Exception:
                    return None

        try:
            item = await self.redis.brpop(QUEUE_NAME, timeout=timeout)
        except Exception:
            self.redis_available = False
            try:
                return await asyncio.wait_for(self.local_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                return None
        if not item:
            return None
        payload = json.loads(item[1])
        return payload["job_id"]

    async def close(self) -> None:
        await self.redis.aclose()
