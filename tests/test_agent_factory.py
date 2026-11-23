from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.ai_gateway.base import AIResponse
from backend.app.api_agent_factory import (
    AgentApprovalRequest,
    AgentCreateRequest,
    AgentFactoryError,
    AgentFactoryService,
)


class FakeDB:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    async def select(self, table, *, params=None):
        rows = list(self.tables.get(table, []))
        params = params or {}
        for key, value in params.items():
            if key in {"select", "order", "limit"}:
                continue
            if value.startswith("eq."):
                expected = value[3:]
                rows = [row for row in rows if str(row.get(key)) == expected]
            elif value.startswith("neq."):
                expected = value[4:]
                rows = [row for row in rows if str(row.get(key)) != expected]
        if "limit" in params:
            rows = rows[: int(params["limit"])]
        return rows

    async def insert(self, table, values):
        row = dict(values)
        row.setdefault("id", str(uuid4()))
        row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self.tables.setdefault(table, []).append(row)
        return row

    async def update(self, table, values, *, where):
        rows = self.tables.setdefault(table, [])
        for row in rows:
            if all(str(row.get(key)) == value.removeprefix("eq.") for key, value in where.items()):
                row.update(values)
                return row
        raise RuntimeError("row not found")

    async def upsert(self, table, values, *, conflict):
        rows = self.tables.setdefault(table, [])
        for row in rows:
            if row.get(conflict) == values.get(conflict):
                row.update(values)
                return row
        return await self.insert(table, values)


class FakeGateway:
    def __init__(self, content="analysis result"):
        self.content = content
        self.calls = []

    async def complete(self, prompt, *, system=None):
        self.calls.append({"prompt": prompt, "system": system})
        return AIResponse(content=self.content, provider="stub-test", model="unit-test")


def valid_request(name="Hermes QA"):
    return AgentCreateRequest(
        name=name,
        role="quality assurance",
        instructions="Analyze test coverage, identify regressions, and report verifiable findings.",
    )


async def create_active_agent(service, name="Hermes QA"):
    row = await service.create_agent(valid_request(name))
    return await service.approve_agent(
        row["id"],
        AgentApprovalRequest(approved=True, approval_note="Owner reviewed the specialist scope."),
    )


@pytest.mark.asyncio
async def test_new_agent_is_draft_and_requires_explicit_owner_approval():
    db = FakeDB()
    service = AgentFactoryService(db, FakeGateway(), execution_enabled=True)

    agent = await service.create_agent(valid_request())

    assert agent["status"] == "draft"
    assert agent["approval_required"] is True
    assert agent["tool_allowlist"] == []
    with pytest.raises(AgentFactoryError) as error:
        await service.run_agent(agent["id"], "Review the test suite carefully.")
    assert error.value.status_code == 409

    with pytest.raises(AgentFactoryError) as error:
        await service.approve_agent(
            agent["id"],
            AgentApprovalRequest(approved=False, approval_note="Not approved for activation."),
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_active_agent_runs_independently_and_persists_operational_memory_without_raw_prompt():
    db = FakeDB()
    gateway = FakeGateway("Coverage is incomplete around retry handling.")
    service = AgentFactoryService(db, gateway, execution_enabled=True)
    agent = await create_active_agent(service)
    prompt = "Review retry behavior and identify missing tests."

    result = await service.run_agent(agent["id"], prompt)

    assert result["status"] == "completed"
    assert result["analysis"] == "Coverage is incomplete around retry handling."
    assert len(gateway.calls) == 1
    run = db.tables["hermes_agent_execution_runs"][0]
    assert run["status"] == "completed"
    assert "prompt" not in run["input"]
    memory = db.tables["hermes_agent_memory"][0]["value"]
    assert memory["total_runs"] == 1
    assert memory["successful_runs"] == 1
    assert memory["failed_runs"] == 0
    assert "raw prompts" in memory["memory_policy"]


@pytest.mark.asyncio
async def test_dynamic_execution_is_disabled_by_default_and_does_not_call_provider():
    db = FakeDB()
    gateway = FakeGateway()
    service = AgentFactoryService(db, gateway, execution_enabled=False)
    agent = await create_active_agent(service)

    with pytest.raises(AgentFactoryError) as error:
        await service.run_agent(agent["id"], "Analyze the API contract.")

    assert error.value.status_code == 503
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_chief_delegates_to_multiple_specialists_as_independent_runs():
    db = FakeDB()
    gateway = FakeGateway()
    service = AgentFactoryService(db, gateway, execution_enabled=True)
    first = await create_active_agent(service, "Hermes QA")
    second = await create_active_agent(service, "Hermes Data")

    result = await service.delegate(
        [first["id"], second["id"]],
        "Analyze the same incident from your specialist perspective.",
    )

    assert result["status"] == "completed"
    assert result["delegated_count"] == 2
    assert len(gateway.calls) == 2
    assert len(db.tables["hermes_agent_execution_runs"]) == 2
    assert len({row["correlation_id"] for row in db.tables["hermes_agent_execution_runs"]}) == 1


def test_agent_permissions_reject_external_actions():
    with pytest.raises(ValueError):
        AgentCreateRequest(
            name="Hermes Publisher",
            role="publisher",
            instructions="This agent would publish external content and change accounts.",
            capabilities=["analysis", "publish"],
            permissions=["ai.complete", "publish"],
        )


def test_dynamic_agent_migration_enforces_approval_and_no_tool_allowlist():
    from pathlib import Path

    migration = Path("supabase/migrations/20261123150000_dynamic_agent_factory.sql").read_text()
    assert "create table if not exists public.hermes_agents" in migration
    assert "create table if not exists public.hermes_agent_execution_runs" in migration
    assert "hermes_agents_activation_requires_approval" in migration
    assert "hermes_agents_no_tools" in migration
    assert "revoke all privileges" in migration
    assert "grant all privileges" in migration
