from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .schemas import HealthResponse, AgentRunRequest, AgentRunResponse, ProductionRequest, ProductionResponse, JobResponse, DashboardResponse
from .ai_gateway.factory import build_ai_gateway
from .agents.registry import AgentRegistry
from .agents.diagnostic import DiagnosticAgent
from .agents.stubs import PassThroughAgent, AGENT_NAMES
from .models.jobs import job_store, JobStatus
from .repositories import ProductStore
from .factory_service import FactoryService

settings = get_settings()
registry = AgentRegistry()
products = ProductStore()
factory: FactoryService | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global factory
    registry.register(DiagnosticAgent(build_ai_gateway(settings)))
    for agent_name in AGENT_NAMES:
        registry.register(PassThroughAgent(agent_name))
    factory = FactoryService(build_ai_gateway(settings), products)
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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

@app.post("/api/v1/factory/produce", response_model=ProductionResponse, tags=["factory"])
async def produce(request: ProductionRequest) -> ProductionResponse:
    if factory is None:
        raise HTTPException(status_code=503, detail="Factory is not ready")
    job = job_store.create("product_factory", {"topic": request.topic})
    job_store.mark_running(job)
    try:
        await factory.produce(request.topic)
        job_store.mark_completed(job)
    except Exception as exc:
        job_store.mark_failed(job, str(exc), retry=False)
        raise HTTPException(status_code=502, detail="Production failed") from exc
    return ProductionResponse(job_id=job.id, status=job.status.value)

@app.get("/api/v1/jobs", response_model=list[JobResponse], tags=["jobs"])
async def list_jobs() -> list[JobResponse]:
    return [JobResponse(id=j.id, job_type=j.job_type, status=j.status.value, attempts=j.attempts, error_message=j.error_message) for j in job_store.jobs.values()]

@app.get("/api/v1/products", tags=["products"])
async def list_products() -> list[dict]:
    return await products.list()

@app.get("/api/v1/dashboard", response_model=DashboardResponse, tags=["dashboard"])
async def dashboard() -> DashboardResponse:
    jobs = list(job_store.jobs.values())
    return DashboardResponse(jobs=len(jobs), products=len(products.products), running=sum(j.status == JobStatus.RUNNING for j in jobs), failures=sum(j.status == JobStatus.FAILED for j in jobs), worker="ready")
