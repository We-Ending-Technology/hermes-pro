from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


async def run_worker_cycle(
    store: Any,
    queue: Any,
    process_product: Callable[[str, Any, Any], Awaitable[Any]],
) -> Any:
    job_id = await queue.dequeue(timeout=10)
    if job_id:
        return await process_product(job_id, store, queue)
    return None
