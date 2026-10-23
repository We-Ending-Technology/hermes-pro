from __future__ import annotations

import asyncio

import pytest

from backend.app import main


@pytest.mark.asyncio
async def test_startup_recovery_resumes_only_nonterminal_product_jobs(monkeypatch):
    jobs = [
        {"id": "pending-1", "job_type": "product_generation", "status": "pending"},
        {"id": "retrying-1", "job_type": "product_generation", "status": "retrying"},
        {"id": "running-1", "job_type": "product_generation", "status": "running"},
        {"id": "done-1", "job_type": "product_generation", "status": "completed"},
        {"id": "opp-1", "job_type": "opportunity_pipeline", "status": "pending"},
        {"id": "agent-1", "job_type": "agent_run", "status": "running"},
    ]

    class FakeStore:
        async def list_jobs(self):
            return jobs

    monkeypatch.setattr(main, "store", FakeStore())
    main._inline_product_tasks.clear()
    started: list[str] = []
    finished = asyncio.Event()

    async def fake_run(job_id: str):
        started.append(job_id)
        if len(started) == 3:
            finished.set()

    monkeypatch.setattr(main, "_run_inline_product", fake_run)

    recovered = await main._recover_inline_product_jobs()
    await asyncio.wait_for(finished.wait(), timeout=1)

    assert recovered == 3
    assert sorted(started) == ["pending-1", "retrying-1", "running-1"]
    assert main._inline_product_tasks == set()
