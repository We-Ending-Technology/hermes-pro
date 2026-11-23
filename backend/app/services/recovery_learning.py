from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


def classify_failure(error_message: str) -> dict[str, Any]:
    """Classify common failures and record a safe, bounded recovery instruction."""
    message = " ".join(str(error_message or "").strip().lower().split())[:500]
    if any(token in message for token in ("429", "503", "timeout", "timed out", "readtimeout", "rate limit", "temporarily unavailable", "connection reset")):
        return {
            "category": "transient_provider",
            "retryable": True,
            "guidance": "Aguardar a janela de recuperação, respeitar os limites do provedor e não alternar para provedor pago sem autorização.",
        }
    if any(token in message for token in ("401", "403", "404", "invalid api key", "authentication", "model not found", "unknown model")):
        return {
            "category": "configuration",
            "retryable": False,
            "guidance": "Tratar como configuração/credencial/modelo inválido; interromper repetição cega e solicitar correção antes de tentar novamente.",
        }
    if any(token in message for token in ("invalid json", "json inválido", "schema", "validation", "incomplete response", "resposta incompleta")):
        return {
            "category": "output_validation",
            "retryable": True,
            "guidance": "Validar a saída estruturada antes de persistir; repetir apenas dentro do limite de tentativas e sem efeitos externos.",
        }
    return {
        "category": "unknown",
        "retryable": True,
        "guidance": "Preservar evidências, respeitar o limite de tentativas e encaminhar para revisão se a falha persistir.",
    }


def memory_key(error_message: str) -> str:
    normalized = " ".join(str(error_message or "").strip().lower().split())[:500]
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    category = classify_failure(normalized)["category"]
    return f"worker_recovery:{category}:{digest}"


async def remember_failure(
    db: Any,
    *,
    job_id: str,
    error_message: str,
    attempt: int,
    max_attempts: int,
) -> dict[str, Any]:
    """Persist a reusable failure pattern in the existing Hermes agent memory table."""
    key = memory_key(error_message)
    existing = await db.select(
        "hermes_agent_memory",
        params={"select": "value", "key": f"eq.{key}", "limit": "1"},
    )
    previous = (existing[0].get("value") or {}) if existing else {}
    classification = classify_failure(error_message)
    now = datetime.now(timezone.utc).isoformat()
    value = {
        **previous,
        **classification,
        "last_error": str(error_message or "")[:500],
        "last_job_id": str(job_id),
        "last_attempt": int(attempt),
        "max_attempts": int(max_attempts),
        "occurrence_count": int(previous.get("occurrence_count") or 0) + 1,
        "last_outcome": "retry_scheduled" if attempt < max_attempts else "needs_review",
        "observed_at": now,
    }
    await db.upsert(
        "hermes_agent_memory",
        {"key": key, "value": value, "source": "worker_recovery", "updated_at": now},
        conflict="key",
    )
    return value


async def mark_recovered(db: Any, *, error_message: str, job_id: str, attempt: int) -> None:
    """Close the learning loop after a later attempt completes successfully."""
    if not str(error_message or "").strip():
        return
    key = memory_key(error_message)
    existing = await db.select(
        "hermes_agent_memory",
        params={"select": "value", "key": f"eq.{key}", "limit": "1"},
    )
    if not existing:
        return
    previous = existing[0].get("value") or {}
    now = datetime.now(timezone.utc).isoformat()
    value = {
        **previous,
        "last_outcome": "recovered",
        "successful_job_id": str(job_id),
        "successful_attempt": int(attempt),
        "recovered_at": now,
    }
    await db.upsert(
        "hermes_agent_memory",
        {"key": key, "value": value, "source": "worker_recovery", "updated_at": now},
        conflict="key",
    )
