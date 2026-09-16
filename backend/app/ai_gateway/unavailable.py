from __future__ import annotations

from .base import AIGateway


class UnavailableAIGateway(AIGateway):
    provider = "unconfigured"
    model = "none"

    async def complete(self, prompt: str, *, system: str | None = None):
        raise RuntimeError("AI Gateway indisponível: nenhuma credencial de IA está configurada")
