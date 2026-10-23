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

@pytest.mark.asyncio
async def test_freelancer_sync_refuses_to_run_while_radar_is_paused(monkeypatch):
    from backend.app import api_autonomy

    monkeypatch.setattr(api_autonomy.settings, "autonomy_enabled", False)
    auth_called = False

    async def forbidden_auth(*args, **kwargs):
        nonlocal auth_called
        auth_called = True
        raise AssertionError("paused sync must stop before authentication or network work")

    monkeypatch.setattr(api_autonomy, "_require_scheduler", forbidden_auth)

    with pytest.raises(HTTPException) as exc:
        await api_autonomy.freelancer_sync()

    assert exc.value.status_code == 409
    assert exc.value.detail == "autonomy disabled"
    assert auth_called is False

