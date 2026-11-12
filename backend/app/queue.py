from __future__ import annotations

import json
from datetime import datetime, timezone

from redis.asyncio import Redis


QUEUE_NAME = "hermes:jobs:product_generation"
AGENT_QUEUE_NAME = "hermes:jobs:agent_run"
PROCESSING_QUEUE_NAME = "hermes:jobs:processing"
AGENT_PROCESSING_QUEUE_NAME = "hermes:jobs:agent_processing"
DEAD_LETTER_QUEUE_NAME = "hermes:jobs:dead_letter"
AGENT_DEAD_LETTER_QUEUE_NAME = "hermes:jobs:agent_dead_letter"


class JobQueue:
    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    async def enqueue(self, job_id: str) -> None:
        await self.redis.lpush(QUEUE_NAME, json.dumps({"job_id": job_id}))

    async def enqueue_agent(self, job_id: str) -> None:
        await self.redis.lpush(AGENT_QUEUE_NAME, json.dumps({"job_id": job_id}))

    async def _move(self, source: str, processing: str, timeout: int) -> str | None:
        raw = await self.redis.blmove(source, processing, timeout, src="RIGHT", dest="LEFT")
        if not raw:
            return None
        payload = json.loads(raw)
        return str(payload["job_id"])

    async def dequeue_agent(self, timeout: int = 1) -> str | None:
        return await self._move(AGENT_QUEUE_NAME, AGENT_PROCESSING_QUEUE_NAME, timeout)

    async def dequeue(self, timeout: int = 10) -> str | None:
        return await self._move(QUEUE_NAME, PROCESSING_QUEUE_NAME, timeout)

    async def ack(self, job_id: str, *, agent: bool = False) -> None:
        processing = AGENT_PROCESSING_QUEUE_NAME if agent else PROCESSING_QUEUE_NAME
        await self.redis.lrem(processing, 1, json.dumps({"job_id": job_id}))

    async def dead_letter(self, job_id: str, *, agent: bool = False, reason: str = "max_attempts_exceeded") -> None:
        processing = AGENT_PROCESSING_QUEUE_NAME if agent else PROCESSING_QUEUE_NAME
        destination = AGENT_DEAD_LETTER_QUEUE_NAME if agent else DEAD_LETTER_QUEUE_NAME
        payload = json.dumps({
            "job_id": job_id,
            "reason": reason[:300],
            "moved_at": datetime.now(timezone.utc).isoformat(),
        })
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.lrem(processing, 1, json.dumps({"job_id": job_id}))
            pipe.lpush(destination, payload)
            await pipe.execute()

    async def remove_processing(self, job_id: str, *, agent: bool = False) -> None:
        processing = AGENT_PROCESSING_QUEUE_NAME if agent else PROCESSING_QUEUE_NAME
        await self.redis.lrem(processing, 0, json.dumps({"job_id": job_id}))

    async def depths(self) -> dict[str, int]:
        return {
            "product": int(await self.redis.llen(QUEUE_NAME)),
            "agent": int(await self.redis.llen(AGENT_QUEUE_NAME)),
            "processing": int(await self.redis.llen(PROCESSING_QUEUE_NAME)),
            "agent_processing": int(await self.redis.llen(AGENT_PROCESSING_QUEUE_NAME)),
            "dead_letter": int(await self.redis.llen(DEAD_LETTER_QUEUE_NAME)),
            "agent_dead_letter": int(await self.redis.llen(AGENT_DEAD_LETTER_QUEUE_NAME)),
        }

    async def close(self) -> None:
        await self.redis.aclose()
