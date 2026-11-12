from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .persistence import PersistentStore
from .telegram import TelegramNotifier

logger = logging.getLogger("hermes.sentinel")


def _age_seconds(value: Any) -> float | None:
    if not value:
        return None
    try:
        checked = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - checked.astimezone(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


async def _record_incident(store: PersistentStore, component: str, symptom: str, cause: str, action: str, result: str, *, resolved: bool, requires_human: bool) -> int:
    rows = await store.db.select(
        "hermes_incidents",
        params={"select": "id,attempts", "component": f"eq.{component}", "status": "eq.open", "limit": "1"},
    )
    now = datetime.now(timezone.utc).isoformat()
    if rows:
        incident = rows[0]
        attempts = int(incident.get("attempts") or 0) + 1
        await store.db.update("hermes_incidents", {
            "symptom": symptom[:500],
            "probable_cause": cause[:700],
            "action": action[:700],
            "result": result[:700],
            "attempts": attempts,
            "requires_human": requires_human,
            "status": "resolved" if resolved else "open",
            "updated_at": now,
            "resolved_at": now if resolved else None,
        }, where={"id": f"eq.{incident['id']}"})
        return attempts
    await store.db.insert("hermes_incidents", {
        "component": component,
        "symptom": symptom[:500],
        "probable_cause": cause[:700],
        "action": action[:700],
        "result": result[:700],
        "attempts": 1,
        "requires_human": requires_human,
        "status": "resolved" if resolved else "open",
        "created_at": now,
        "updated_at": now,
        "resolved_at": now if resolved else None,
    })
    return 1


async def sentinel_tick(settings: Any, store: PersistentStore, queue) -> dict[str, Any]:
    """Check live dependencies and recover stale persisted jobs without inventing health."""
    checks: dict[str, bool] = {}
    details: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
            response = await client.get(settings.hermes_public_api_url.rstrip("/") + "/health")
            checks["api"] = response.is_success
            details["api"] = f"HTTP {response.status_code}"
    except Exception as exc:
        checks["api"] = False
        details["api"] = f"{type(exc).__name__}: {str(exc)[:250]}"

    try:
        checks["redis"] = bool(await queue.redis.ping())
        details["redis"] = "PING ok" if checks["redis"] else "PING returned false"
    except Exception as exc:
        checks["redis"] = False
        details["redis"] = f"{type(exc).__name__}: {str(exc)[:250]}"

    try:
        checks["postgres"] = bool(await store.db.health())
        details["postgres"] = "Supabase REST health ok" if checks["postgres"] else "database health failed"
    except Exception as exc:
        checks["postgres"] = False
        details["postgres"] = f"{type(exc).__name__}: {str(exc)[:250]}"

    worker_rows = await store.db.select(
        "hermes_system_health",
        params={"select": "status,checked_at,message", "component": "eq.worker", "limit": "1"},
    )
    worker = worker_rows[0] if worker_rows else {}
    worker_age = _age_seconds(worker.get("checked_at"))
    checks["worker"] = bool(worker and worker.get("status") == "ok" and worker_age is not None and worker_age <= 90)
    details["worker"] = f"heartbeat age={round(worker_age)}s" if worker_age is not None else "heartbeat missing or invalid"

    results = {}
    for component, healthy in checks.items():
        if healthy:
            open_rows = await store.db.select(
                "hermes_incidents",
                params={"select": "id", "component": f"eq.{component}", "status": "eq.open", "limit": "1"},
            )
            if open_rows:
                now = datetime.now(timezone.utc).isoformat()
                await store.db.update("hermes_incidents", {
                    "status": "resolved",
                    "result": "componente voltou a responder no health check",
                    "requires_human": False,
                    "updated_at": now,
                    "resolved_at": now,
                }, where={"id": f"eq.{open_rows[0]['id']}"})
            results[component] = "healthy"
            continue

        action = "verificar dependência e executar recuperação segura"
        result = "dependência continua indisponível"
        resolved = False
        if component == "worker":
            try:
                from worker.main import recover_pending
                await recover_pending(store, queue)
                action = "recolocar tarefas persistentes órfãs na fila"
                result = "varredura de recuperação executada; heartbeat ainda precisa voltar"
            except Exception as exc:
                result = f"recuperação falhou: {type(exc).__name__}: {str(exc)[:250]}"
        attempts = await _record_incident(
            store,
            component,
            details[component],
            "falha de health check ou heartbeat ausente/atrasado",
            action,
            result,
            resolved=resolved,
            requires_human=False,
        )
        if attempts == 3:
            await _record_incident(
                store, component, details[component],
                "falha persistente após três verificações",
                action, result, resolved=False, requires_human=True,
            )
            await TelegramNotifier(settings).send(
                f"Hermes Sentinel: intervenção humana necessária. Componente: {component}. "
                f"Sintoma: {details[component]}. Ação tentada: {action}."
            )
        results[component] = "incident_open"

    return {"status": "healthy" if all(checks.values()) else "degraded", "checks": checks, "details": details, "results": results}


async def run_sentinel(settings: Any, store: PersistentStore, queue, interval_seconds: int = 60) -> None:
    logger.info("Hermes Sentinel started interval_seconds=%s", interval_seconds)
    while True:
        try:
            result = await sentinel_tick(settings, store, queue)
            logger.info("sentinel_tick result=%s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("sentinel tick failed")
        await asyncio.sleep(interval_seconds)
