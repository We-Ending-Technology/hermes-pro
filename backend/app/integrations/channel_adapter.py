from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ChannelAdapter(ABC):
    name: str

    @abstractmethod
    async def create_product(self, product: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def upload_file(self, product_id: str, path: str, content: bytes, content_type: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def set_price(self, product_id: str, price: float) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def publish(self, product_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_product(self, product_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_sales(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_orders(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_status(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def receive_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
