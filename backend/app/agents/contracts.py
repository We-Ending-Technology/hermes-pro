from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class AgentContract:
    name: str
    capabilities: tuple[str, ...]
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
