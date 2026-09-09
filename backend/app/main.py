from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .schemas import HealthResponse, AgentRunRequest, AgentRunResponse
from .ai_gateway.factory import build_ai_gateway
from .agents.registry import AgentRegistry
from .agents.diagnostic import DiagnosticAgent
from .agents.stubs import PassThroughAgent, AGENT_NAMES

settings = get_settings()
registry = AgentRegistry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.register(DiagnosticAgent(build_ai_gateway(settings)))
    for agent_name in AGENT_NAMES:
        registry.register(PassThroughAgent(agent_name))
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "hermes-pro-api"}

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="hermes-pro-api", environment=settings.app_env)

@app.get("/api/v1/agents", tags=["agents"])
async def list_agents() -> dict[str, list[str]]:
    return {"agents": registry.names()}

@app.post("/api/v1/agents/run", response_model=AgentRunResponse, tags=["agents"])
async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    try:
        agent = registry.get(request.agent)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    output = await agent.run(request.input)
    return AgentRunResponse(run_id=str(uuid4()), agent=request.agent, status="completed", output=output)
