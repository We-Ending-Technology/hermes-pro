from abc import ABC, abstractmethod
from enum import StrEnum

class NotificationEvent(StrEnum):
    JOB_COMPLETED = "job_completed"
    PRODUCT_CREATED = "product_created"
    PUBLICATION_COMPLETED = "publication_completed"
    SALE_RECEIVED = "sale_received"
    CRITICAL_ERROR = "critical_error"
    EVOLUTION_AVAILABLE = "evolution_available"

class TelegramNotifier(ABC):
    @abstractmethod
    async def notify(self, event: NotificationEvent, payload: dict) -> None:
        raise NotImplementedError

class StubTelegramNotifier(TelegramNotifier):
    async def notify(self, event: NotificationEvent, payload: dict) -> None:
        return None

class MarketplaceAdapter(ABC):
    """Future boundary for Mercado Livre, Shopee, Amazon and other channels."""
    name: str

    @abstractmethod
    async def publish(self, product: dict) -> dict:
        raise NotImplementedError
