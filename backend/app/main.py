from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .schemas import HealthResponse, AgentRunRequest, AgentRunResponse, ProductionRequest, ProductionResponse, JobResponse, DashboardResponse, ChatRequest, ChatResponse, AutoProductionResponse
from .ai_gateway.factory import build_ai_gateway
from .agents.registry import AgentRegistry
from .agents.diagnostic import DiagnosticAgent
from .agents.stubs import PassThroughAgent, AGENT_NAMES
from .models.jobs import job_store, JobStatus
from .repositories import ProductStore, SupabaseRepository, PersistentJobStore, PersistentProductStore
from .factory_service import FactoryService
from .planner import TopicPlanner

settings = get_settings()
registry = AgentRegistry()
repository = SupabaseRepository(settings)
job_store_persistent = PersistentJobStore(repository)
products_persistent = PersistentProductStore(repository)
products = ProductStore()
factory: FactoryService | None = None
gateway = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global factory, gateway
    gateway = build_ai_gateway(settings)
    registry.register(DiagnosticAgent(gateway))
    for agent_name in AGENT_NAMES:
        registry.register(PassThroughAgent(agent_name))
    factory = FactoryService(gateway, products_persistent if settings.supabase_configured else products, repository=repository if settings.supabase_configured else None, storage_bucket=settings.storage_bucket)
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

@app.post("/api/v1/chat", response_model=ChatResponse, tags=["hermes"])
async def chat(request: ChatRequest) -> ChatResponse:
    if gateway is None:
        raise HTTPException(status_code=503, detail="Hermes is not ready")
    response = await gateway.complete(request.message, system="You are Hermes, the operations assistant. Be concise, honest about capabilities, and never claim an action happened unless the API confirms it.")
    return ChatResponse(response=response.content, provider=response.provider, model=response.model)

@app.post("/api/v1/factory/produce", response_model=ProductionResponse, tags=["factory"])
async def produce(request: ProductionRequest) -> ProductionResponse:
    if factory is None:
        raise HTTPException(status_code=503, detail="Factory is not ready")
    if settings.supabase_configured:
        job = await job_store_persistent.create("product_factory", {"topic": request.topic})
        return ProductionResponse(job_id=job["id"], status="pending")
    else:
        job = job_store.create("product_factory", {"topic": request.topic})
        job_store.mark_running(job)
        job_id = job.id
    try:
        await factory.produce(request.topic)
        if settings.supabase_configured:
            await job_store_persistent.update(job_id, status="completed")
        else:
            job_store.mark_completed(job)
    except Exception as exc:
        if settings.supabase_configured:
            await job_store_persistent.update(job_id, status="failed", error_message=str(exc))
        else:
            job_store.mark_failed(job, str(exc), retry=False)
        raise HTTPException(status_code=502, detail="Production failed") from exc
    return ProductionResponse(job_id=job_id, status="completed")

@app.post("/api/v1/factory/auto-topic", response_model=AutoProductionResponse, tags=["factory"])
async def auto_topic() -> AutoProductionResponse:
    if not settings.auto_production_enabled:
        raise HTTPException(status_code=409, detail="Automatic production is disabled; set AUTO_PRODUCTION_ENABLED=true on the server")
    if not settings.supabase_configured:
        raise HTTPException(status_code=503, detail="Automatic production requires Supabase")
    if gateway is None:
        raise HTTPException(status_code=503, detail="Hermes is not ready")
    topic = await TopicPlanner(gateway).next_topic()
    job = await job_store_persistent.create("product_factory", {"topic": topic}) if settings.supabase_configured else job_store.create("product_factory", {"topic": topic})
    job_id = job["id"] if isinstance(job, dict) else job.id
    return AutoProductionResponse(topic=topic, job_id=job_id, status="pending")

@app.get("/api/v1/jobs", response_model=list[JobResponse], tags=["jobs"])
async def list_jobs() -> list[JobResponse]:
    if settings.supabase_configured:
        rows = await repository.list("jobs", {"select": "*", "order": "created_at.desc"})
        return [JobResponse(id=row["id"], job_type=row["job_type"], status=row["status"], attempts=row["attempts"], error_message=row.get("error_message")) for row in rows]
    return [JobResponse(id=j.id, job_type=j.job_type, status=j.status.value, attempts=j.attempts, error_message=j.error_message) for j in job_store.jobs.values()]

@app.get("/api/v1/products", tags=["products"])
async def list_products() -> list[dict]:
    if settings.supabase_configured:
        return await products_persistent.list()
    return await products.list()

@app.get("/api/v1/dashboard", response_model=DashboardResponse, tags=["dashboard"])
async def dashboard() -> DashboardResponse:
    if settings.supabase_configured:
        jobs = await repository.list("jobs", {"select": "status"})
        products_rows = await repository.list("products", {"select": "id"})
        return DashboardResponse(jobs=len(jobs), products=len(products_rows), running=sum(j["status"] == "running" for j in jobs), failures=sum(j["status"] == "failed" for j in jobs), worker="configured")
    jobs = list(job_store.jobs.values())
    return DashboardResponse(jobs=len(jobs), products=len(products.products), running=sum(j.status == JobStatus.RUNNING for j in jobs), failures=sum(j.status == JobStatus.FAILED for j in jobs), worker="ready")
