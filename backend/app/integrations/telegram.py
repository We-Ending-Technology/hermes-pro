from __future__ import annotations

from typing import Any

import httpx


class TelegramNotifier:
    def __init__(self, bot_token: str | None, chat_id: str | None) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send(self, event: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            return {"status": "not_configured"}
        text = event.get("message") or f"Hermes: {event.get('event_type', 'event')}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json={"chat_id": self.chat_id, "text": text})
        if response.is_error:
            return {"status": "error", "http_status": response.status_code}
        return {"status": "sent"}
