from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app import main


@pytest.mark.asyncio
async def test_autonomy_pause_blocks_all_cycle_entry_points(monkeypatch):
    monkeypatch.setattr(main.settings, "autonomy_enabled", False)
    called = False

    async def forbidden_cycle(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("discovery must not run while autonomy is paused")

    monkeypatch.setattr(main.autonomy_service, "cycle", forbidden_cycle)

    with pytest.raises(HTTPException) as exc:
        await main._run_autonomy_once()

    assert exc.value.status_code == 409
    assert exc.value.detail == "autonomy disabled"
    assert called is False
