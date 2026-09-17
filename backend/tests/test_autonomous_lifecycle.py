import pytest

from app.main import autonomous_cycle_once


@pytest.mark.asyncio
async def test_autonomous_cycle_runs_watchdog_before_production(monkeypatch):
    calls = []

    async def watchdog():
        calls.append("watchdog")
        return {"incidents": 0}

    async def discover():
        calls.append("discover")

    async def orchestrate():
        calls.append("orchestrate")

    monkeypatch.setattr("app.main.run_watchdog", watchdog)
    monkeypatch.setattr("app.main.discover_public_signals", discover)
    monkeypatch.setattr("app.main.run_autonomous_orchestration", orchestrate)
    await autonomous_cycle_once()
    assert calls == ["watchdog", "discover", "orchestrate"]
