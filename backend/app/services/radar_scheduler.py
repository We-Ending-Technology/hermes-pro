from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .autonomous_cycle import discover_public_signals
from .commerce_store import CommerceStore
from .orchestrator import AutonomousOrchestrator
from ..db.supabase import SupabaseREST


async def run_radar_cycle(
    commerce: CommerceStore,
    db: SupabaseREST,
    orchestrator: AutonomousOrchestrator | None = None,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    signals = await discover_public_signals(commerce, limit=24)
    execution = None
    if orchestrator is not None:
        execution = await orchestrator.run_cycle(limit=3)
    return {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started,
        "sources": {"google_trends_and_news": len(signals)},
        "total": len(signals),
        "execution": execution,
    }


async def radar_scheduler_loop(
    commerce: CommerceStore,
    db: SupabaseREST,
    controls: Any,
    orchestrator: AutonomousOrchestrator | None = None,
    interval_seconds: int = 900,
) -> None:
    while True:
        try:
            status = controls.get_status()
            if not status.get("kill_switches", {}).get("global") and not status.get("settings", {}).get("pause_radar"):
                await run_radar_cycle(commerce, db, orchestrator)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)
