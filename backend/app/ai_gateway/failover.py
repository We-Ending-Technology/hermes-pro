from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .base import AIGateway, AIResponse


@dataclass(frozen=True)
class ProviderSlot:
    provider: str
    key_index: int
    gateway: AIGateway


class FailoverAIGateway(AIGateway):
    """Try configured provider/key slots in priority order.

    Secrets stay in environment configuration; this layer only stores adapter
    instances and never exposes key material in responses or diagnostics.
    """

    def __init__(self, slots: list[ProviderSlot]) -> None:
        if not slots:
            raise ValueError("At least one AI provider slot is required")
        self.slots = slots

    @property
    def configured_providers(self) -> list[str]:
        return list(dict.fromkeys(slot.provider for slot in self.slots))

    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        failures: list[str] = []
        for slot in self.slots:
            try:
                return await slot.gateway.complete(prompt, system=system)
            except Exception as exc:
                failures.append(f"{slot.provider}[{slot.key_index}]: {type(exc).__name__}")
        raise RuntimeError("All configured AI provider slots failed: " + "; ".join(failures))
