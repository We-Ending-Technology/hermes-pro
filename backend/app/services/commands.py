from __future__ import annotations

import re
from typing import Any


def parse_command(message: str) -> dict[str, Any] | None:
    text = " ".join(message.strip().split())
    normalized = text.lower()

    if normalized in {"encontre oportunidades", "encontre oportunidades para hoje", "radar oportunidades"}:
        return {"action": "find_opportunities"}

    if normalized in {"procure trabalhos freelance", "encontre serviços", "encontre trabalhos freelance"}:
        return {"action": "find_services"}

    if normalized in {"pause tudo", "pare tudo", "pausar tudo"}:
        return {"action": "pause_all"}

    if normalized in {"retome tudo", "resume tudo", "retomar tudo"}:
        return {"action": "resume_all"}

    match = re.match(r"^(?:crie|criar) (?:um )?(?:ebook|produto) sobre (.+)$", text, re.IGNORECASE)
    if match:
        return {"action": "create_product", "topic": match.group(1).strip()}

    match = re.match(r"^mude(?: o)? preço(?: do produto)?\s*(?:para)?\s*R\$\s*([0-9]+(?:[.,][0-9]{1,2})?)$", text, re.IGNORECASE)
    if match:
        return {"action": "set_price", "price": float(match.group(1).replace(",", "."))}

    return None
