from __future__ import annotations

from datetime import datetime
import re
from typing import Any


async def handle_chat_command(message: str, store: Any, queue: Any) -> dict[str, str] | None:
    text = message.strip()
    normalized = re.sub(r"\s+", " ", text.lower())

    if any(phrase in normalized for phrase in ("que dia é hoje", "que dia e hoje", "qual a data de hoje", "data de hoje")):
        now = datetime.now().astimezone()
        return {
            "response": f"Hoje é {now.strftime('%d/%m/%Y')} ({now.strftime('%A')}).",
            "provider": "system",
            "model": "clock",
        }

    product_match = re.search(r"(?:produza|crie|gere|faça|faca|faz)\s+(?:um\s+)?(?:ebook|e-book|livro digital)(?:\s+(?:sobre|de|com o tema)\s+(.+))?", normalized, re.I)
    if product_match:
        topic = (product_match.group(1) or "produtividade prática").strip(" .")
        product, job = await store.create_product_and_job(topic, {"source": "chat"}, None)
        await queue.enqueue(str(job["id"]))
        return {
            "response": f"Iniciei a produção do e-book sobre {topic}. Job: {job['id']}.",
            "provider": "system",
            "model": "command",
        }

    return None
