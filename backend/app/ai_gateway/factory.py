from .adapters import GeminiAdapter, OpenAIAdapter
from .base import AIGateway
from .failover import FailoverAIGateway, ProviderSlot
from .stub import StubAIGateway
from ..core.config import Settings


def build_ai_gateway(settings: Settings) -> AIGateway:
    if settings.ai_provider.strip().lower() == "stub":
        return StubAIGateway()

    slots: list[ProviderSlot] = []
    pools = {
        "gemini": settings.gemini_api_key_pool,
        "openai": settings.openai_api_key_pool,
    }
    for provider in settings.provider_order_list:
        for index, key in enumerate(pools.get(provider, []), start=1):
            if provider == "gemini":
                gateway = GeminiAdapter(api_key=key, model=settings.gemini_model)
            elif provider == "openai":
                gateway = OpenAIAdapter(api_key=key, model=settings.openai_model)
            else:
                continue
            slots.append(ProviderSlot(provider=provider, key_index=index, gateway=gateway))

    if not slots:
        raise ValueError("No configured AI provider keys found")
    # Preserve the established single-provider contract while enabling
    # failover whenever multiple configured slots are available.
    if len(slots) == 1:
        return slots[0].gateway
    return FailoverAIGateway(slots)
