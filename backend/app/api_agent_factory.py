from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from .ai_gateway.base import AIGateway
from .core.config import Settings
from .db.supabase import SupabaseREST


_ALLOWED_CAPABILITIES = {"analysis"}
_ALLOWED_PERMISSIONS = {"ai.complete", "memory.read", "memory.write"}
_MAX_DELEGATION = 3


class AgentFactoryError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    role: str = Field(min_length=3, max_length=80)
    instructions: str = Field(min_length=30, max_length=4000)
    capabilities: list[str] = Field(default_factory=lambda: ["analysis"], max_length=3)
    permissions: list[str] = Field(
        default_factory=lambda: ["ai.complete", "memory.read", "memory.write"],
        max_length=3,
    )

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, value: list[str]) -> list[str]:
        if not value or len(value) != len(set(value)) or not set(value).issubset(_ALLOWED_CAPABILITIES):
            raise ValueError("Only the analysis capability is currently available.")
        return value

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        if "ai.complete" not in value or len(value) != len(set(value)) or not set(value).issubset(_ALLOWED_PERMISSIONS):
            raise ValueError("Permissions must be a unique allowlisted subset and include ai.complete.")
        return value


class AgentApprovalRequest(BaseModel):
    approved: bool
    approval_note: str = Field(min_length=10, max_length=300)


class AgentRunRequest(BaseModel):
    prompt: str = Field(min_length=8, max_length=4000)


class ChiefDelegateRequest(BaseModel):
    agent_ids: list[str] = Field(min_length=1, max_length=_MAX_DELEGATION)
    prompt: str = Field(min_length=8, max_length=4000)

    @field_validator("agent_ids")
    @classmethod
    def unique_agents(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("agent_ids must be unique.")
        return value


class ChiefProposeAgentRequest(BaseModel):
    objective: str = Field(min_length=20, max_length=2000)
    desired_role: str = Field(min_length=3, max_length=80)


class AgentFactoryService:
    def __init__(self, db: SupabaseREST, gateway: AIGateway, *, execution_enabled: bool = False) -> None:
        self.db = db
        self.gateway = gateway
        self.execution_enabled = execution_enabled

    @staticmethod
    def _slug(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
        return slug[:80].strip("-")

    async def list_agents(self, *, include_disabled: bool = True) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": "*", "order": "created_at.asc"}
        if not include_disabled:
            params["status"] = "neq.disabled"
        return await self.db.select("hermes_agents", params=params)

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        rows = await self.db.select(
            "hermes_agents",
            params={"select": "*", "id": f"eq.{agent_id}", "limit": "1"},
        )
        if not rows:
            raise AgentFactoryError(404, "Agent not found.")
        return rows[0]

    async def create_agent(self, request: AgentCreateRequest) -> dict[str, Any]:
        slug = self._slug(request.name)
        if not slug:
            raise AgentFactoryError(422, "Agent name must contain letters or numbers.")
        existing = await self.db.select(
            "hermes_agents",
            params={"select": "id", "slug": f"eq.{slug}", "limit": "1"},
        )
        if existing:
            raise AgentFactoryError(409, "An agent with this name already exists.")
        now = datetime.now(timezone.utc).isoformat()
        try:
            return await self.db.insert("hermes_agents", {
                "slug": slug,
                "name": request.name.strip(),
                "role": request.role.strip(),
                "instructions": request.instructions.strip(),
                "capabilities": request.capabilities,
                "permissions": request.permissions,
                "tool_allowlist": [],
                "status": "draft",
                "approval_required": True,
                "approved_at": None,
                "approved_by": None,
                "approval_note": None,
                "version": 1,
                "created_by": "hermes_private_api",
                "created_at": now,
                "updated_at": now,
            })
        except Exception as exc:
            # The database unique constraint is the final race-safe duplicate guard.
            if "duplicate" in str(exc).casefold() or "unique" in str(exc).casefold():
                raise AgentFactoryError(409, "An agent with this name already exists.") from exc
            raise

    async def approve_agent(self, agent_id: str, request: AgentApprovalRequest) -> dict[str, Any]:
        if not request.approved:
            raise AgentFactoryError(409, "Activation requires an explicit owner approval.")
        agent = await self.get_agent(agent_id)
        if agent.get("status") == "disabled":
            raise AgentFactoryError(409, "Disabled agents cannot be activated; create a reviewed new version.")
        now = datetime.now(timezone.utc).isoformat()
        return await self.db.update(
            "hermes_agents",
            {
                "status": "active",
                "approval_required": False,
                "approved_at": now,
                "approved_by": "private_api_owner",
                "approval_note": request.approval_note.strip(),
                "updated_at": now,
            },
            where={"id": f"eq.{agent_id}"},
        )

    async def disable_agent(self, agent_id: str) -> dict[str, Any]:
        await self.get_agent(agent_id)
        return await self.db.update(
            "hermes_agents",
            {"status": "disabled", "updated_at": datetime.now(timezone.utc).isoformat()},
            where={"id": f"eq.{agent_id}"},
        )

    async def _memory(self, agent: dict[str, Any]) -> dict[str, Any]:
        if "memory.read" not in (agent.get("permissions") or []):
            return {}
        key = f"dynamic_agent:{agent['id']}"
        rows = await self.db.select(
            "hermes_agent_memory",
            params={"select": "value", "key": f"eq.{key}", "limit": "1"},
        )
        value = rows[0].get("value") if rows else {}
        return value if isinstance(value, dict) else {}

    async def _save_memory(self, agent: dict[str, Any], *, success: bool, provider: str | None = None,
                           model: str | None = None, error_class: str | None = None) -> None:
        if "memory.write" not in (agent.get("permissions") or []):
            return
        key = f"dynamic_agent:{agent['id']}"
        previous = await self._memory(agent)
        total = int(previous.get("total_runs") or 0) + 1
        succeeded = int(previous.get("successful_runs") or 0) + (1 if success else 0)
        failed = int(previous.get("failed_runs") or 0) + (0 if success else 1)
        value = {
            "agent_id": str(agent["id"]),
            "agent_version": int(agent.get("version") or 1),
            "total_runs": total,
            "successful_runs": succeeded,
            "failed_runs": failed,
            "last_status": "completed" if success else "failed",
            "last_provider": provider,
            "last_model": model,
            "last_error_class": error_class,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "memory_policy": "Operational metadata only; raw prompts and secrets are not persisted here.",
        }
        await self.db.upsert(
            "hermes_agent_memory",
            {"key": key, "value": value, "source": "dynamic_agent_factory", "updated_at": value["updated_at"]},
            conflict="key",
        )

    async def run_agent(self, agent_id: str, prompt: str, *, correlation_id: str | None = None) -> dict[str, Any]:
        if not self.execution_enabled:
            raise AgentFactoryError(503, "Dynamic agent execution is disabled until the owner explicitly enables it after budget review.")
        agent = await self.get_agent(agent_id)
        if agent.get("status") != "active" or agent.get("approval_required"):
            raise AgentFactoryError(409, "Only owner-approved active agents may execute.")
        permissions = set(agent.get("permissions") or [])
        capabilities = set(agent.get("capabilities") or [])
        if "analysis" not in capabilities or "ai.complete" not in permissions:
            raise AgentFactoryError(403, "This agent lacks the required allowlisted analysis permission.")
        if agent.get("tool_allowlist") not in (None, []):
            raise AgentFactoryError(403, "External tools are not enabled for dynamic agents.")

        correlation = correlation_id or str(uuid4())
        fingerprint = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        run = await self.db.insert("hermes_agent_execution_runs", {
            "correlation_id": correlation,
            "agent_id": str(agent["id"]),
            "status": "running",
            "input": {"prompt_length": len(prompt), "prompt_sha256": fingerprint},
            "output": {},
            "started_at": now,
            "created_at": now,
        })
        try:
            memory = await self._memory(agent)
            memory_context = (
                f"Operational memory: total runs={memory.get('total_runs', 0)}, "
                f"successful={memory.get('successful_runs', 0)}, failed={memory.get('failed_runs', 0)}, "
                f"last status={memory.get('last_status', 'none')}, "
                f"last error class={memory.get('last_error_class', 'none')}."
            )
            system = (
                f"You are {agent['name']}, specialist role: {agent['role']}.\\n"
                f"Operating instructions: {agent['instructions']}\\n"
                f"{memory_context}\\n"
                "Return a factual, concise analysis with assumptions and risks separated. "
                "You have no external tools and cannot publish, spend money, modify accounts, deploy code, "
                "send messages, or claim to have completed external actions."
            )
            response = await self.gateway.complete(prompt, system=system)
            output = {
                "agent_id": str(agent["id"]),
                "agent": agent["name"],
                "analysis": response.content[:16000],
                "provider": response.provider,
                "model": response.model,
            }
            completed_at = datetime.now(timezone.utc).isoformat()
            await self.db.update(
                "hermes_agent_execution_runs",
                {"status": "completed", "output": output, "provider": response.provider,
                 "model": response.model, "completed_at": completed_at},
                where={"id": f"eq.{run['id']}"},
            )
            await self._save_memory(agent, success=True, provider=response.provider, model=response.model)
            return {"run_id": str(run["id"]), "correlation_id": correlation, "status": "completed", **output}
        except Exception as exc:
            await self.db.update(
                "hermes_agent_execution_runs",
                {"status": "failed", "error_message": type(exc).__name__,
                 "completed_at": datetime.now(timezone.utc).isoformat()},
                where={"id": f"eq.{run['id']}"},
            )
            try:
                await self._save_memory(agent, success=False, error_class=type(exc).__name__)
            except Exception:
                pass
            if isinstance(exc, AgentFactoryError):
                raise
            raise AgentFactoryError(502, f"Agent execution failed ({type(exc).__name__}); run {run['id']} was recorded.") from exc

    async def delegate(self, agent_ids: list[str], prompt: str) -> dict[str, Any]:
        if not self.execution_enabled:
            raise AgentFactoryError(503, "Dynamic agent execution is disabled until the owner explicitly enables it after budget review.")
        if not 1 <= len(agent_ids) <= _MAX_DELEGATION:
            raise AgentFactoryError(422, f"Chief may delegate to 1–{_MAX_DELEGATION} specialists per run.")
        correlation = str(uuid4())
        results = await asyncio.gather(
            *(self.run_agent(agent_id, prompt, correlation_id=correlation) for agent_id in agent_ids),
            return_exceptions=True,
        )
        delegated = []
        for agent_id, result in zip(agent_ids, results):
            if isinstance(result, Exception):
                delegated.append({
                    "agent_id": agent_id,
                    "status": "failed",
                    "error": result.detail if isinstance(result, AgentFactoryError) else type(result).__name__,
                })
            else:
                delegated.append(result)
        return {
            "correlation_id": correlation,
            "chief": "Hermes Chefe",
            "status": "completed" if all(item["status"] == "completed" for item in delegated) else "partial",
            "delegated_count": len(delegated),
            "results": delegated,
        }

    async def propose_agent(self, objective: str, desired_role: str) -> dict[str, Any]:
        if not self.execution_enabled:
            raise AgentFactoryError(503, "AI agent design is disabled until the owner explicitly enables it after budget review.")
        response = await self.gateway.complete(
            "Design one narrowly scoped Hermes specialist. Return only valid JSON with keys name, role, instructions. "
            "The instructions must be at least 30 characters and must explicitly forbid external actions, spending, publishing, "
            "account changes, secret access and deployment.\n"
            f"Desired role: {desired_role}\nObjective: {objective}",
            system="You are Hermes Chefe, responsible for designing least-privilege specialist agents. "
                   "The new agent can perform analysis only and has no tools.",
        )
        try:
            spec = json.loads(response.content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AgentFactoryError(502, "Chief returned invalid JSON while proposing the specialist.") from exc
        if not isinstance(spec, dict):
            raise AgentFactoryError(502, "Chief returned an invalid specialist definition.")
        request = AgentCreateRequest(
            name=spec.get("name", ""),
            role=spec.get("role", desired_role),
            instructions=spec.get("instructions", ""),
            capabilities=["analysis"],
            permissions=["ai.complete", "memory.read", "memory.write"],
        )
        agent = await self.create_agent(request)
        return {"agent": agent, "status": "draft", "provider": response.provider, "model": response.model,
                "approval_required": True}


def create_agent_factory_router(db: SupabaseREST, gateway: AIGateway, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1/agent-factory", tags=["agent-factory"])
    service = AgentFactoryService(
        db, gateway,
        execution_enabled=bool(getattr(settings, "dynamic_agent_execution_enabled", False)),
    )

    def raise_http(exc: AgentFactoryError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @router.get("/agents")
    async def list_agents(include_disabled: bool = True):
        try:
            return {"agents": await service.list_agents(include_disabled=include_disabled)}
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Agent registry is unavailable.") from exc

    @router.get("/agents/{agent_id}")
    async def get_agent(agent_id: str):
        try:
            return await service.get_agent(agent_id)
        except AgentFactoryError as exc:
            raise_http(exc)

    @router.post("/agents", status_code=201)
    async def create_agent(request: AgentCreateRequest):
        try:
            return await service.create_agent(request)
        except AgentFactoryError as exc:
            raise_http(exc)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Could not persist the draft agent.") from exc

    @router.post("/agents/{agent_id}/activate")
    async def activate_agent(agent_id: str, request: AgentApprovalRequest):
        try:
            return await service.approve_agent(agent_id, request)
        except AgentFactoryError as exc:
            raise_http(exc)

    @router.post("/agents/{agent_id}/disable")
    async def disable_agent(agent_id: str):
        try:
            return await service.disable_agent(agent_id)
        except AgentFactoryError as exc:
            raise_http(exc)

    @router.post("/agents/{agent_id}/run")
    async def run_agent(agent_id: str, request: AgentRunRequest):
        try:
            return await service.run_agent(agent_id, request.prompt)
        except AgentFactoryError as exc:
            raise_http(exc)

    @router.post("/chief/propose-agent", status_code=201)
    async def propose_agent(request: ChiefProposeAgentRequest):
        try:
            return await service.propose_agent(request.objective, request.desired_role)
        except AgentFactoryError as exc:
            raise_http(exc)

    @router.post("/chief/delegate")
    async def chief_delegate(request: ChiefDelegateRequest):
        try:
            return await service.delegate(request.agent_ids, request.prompt)
        except AgentFactoryError as exc:
            raise_http(exc)

    @router.get("/runs")
    async def list_runs(limit: int = 50):
        if not 1 <= limit <= 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100.")
        try:
            return {"runs": await db.select(
                "hermes_agent_execution_runs",
                params={"select": "*", "order": "created_at.desc", "limit": str(limit)},
            )}
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Agent execution history is unavailable.") from exc

    return router
