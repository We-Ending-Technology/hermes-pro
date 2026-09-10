from contextlib import asynccontextmanager
from datetime import date
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .ai_gateway.factory import build_ai_gateway
from .agents.diagnostic import DiagnosticAgent
from .agents.registry import AgentRegistry
from .agents.stubs import AGENT_NAMES, PassThroughAgent
from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .queue import JobQueue
from .schemas import *
from .services.analytics import analytics_service
from .services.integrations import integration_service
from .services.persistence import PersistentStore
from .services.quality import quality_service
from .services.radar import radar_service
from .services.sales import sales_service

settings = get_settings()
ai_gateway = build_ai_gateway(settings)
registry = AgentRegistry()
db = SupabaseREST(settings)
store = PersistentStore(db)
queue = JobQueue(settings.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.register(DiagnosticAgent(ai_gateway))
    for agent_name in AGENT_NAMES:
        registry.register(PassThroughAgent(agent_name))
    yield
    await queue.close()


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def product_response(row: dict) -> ProductResponse:
    metadata = dict(row.get("metadata") or {})
    metadata["job_id"] = row.get("job_id")
    return ProductResponse(id=str(row["id"]), topic=row["topic"], title=row.get("title"), status=row["status"], current_stage=row["current_stage"], stages=list(__import__("backend.app.product_factory", fromlist=["PIPELINE_STAGES"]).PIPELINE_STAGES), metadata=metadata, created_at=row["created_at"])


def job_response(row: dict) -> JobResponse:
    return JobResponse(id=str(row["id"]), job_type=row["job_type"], status=row["status"], attempts=row["attempts"], max_attempts=row["max_attempts"], error_message=row.get("error_message"), payload=row.get("payload") or {}, created_at=row["created_at"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "hermes-pro-api"}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="hermes-pro-api", environment=settings.app_env)


@app.get("/api/v1/agents")
async def list_agents() -> dict[str, list[str]]:
    return {"agents": registry.names()}


@app.post("/api/v1/agents/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    try:
        agent = registry.get(request.agent)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    output = await agent.run(request.input)
    return AgentRunResponse(run_id=str(uuid4()), agent=request.agent, status="completed", output=output)


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    result = await ai_gateway.complete(request.message, system="You are Hermes Pro, an operations assistant for digital products. Be concise, truthful, and never invent sales, integrations, or completed jobs.")
    return ChatResponse(response=result.content, provider=result.provider, model=result.model)


@app.get("/api/v1/integrations", response_model=list[IntegrationStatus])
async def integrations() -> list[IntegrationStatus]:
    return [IntegrationStatus(**item) for item in integration_service.status()]


@app.get("/api/v1/jobs", response_model=list[JobResponse])
async def jobs() -> list[JobResponse]:
    return [job_response(row) for row in await store.list_jobs()]


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    row = await store.get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    return job_response(row)


@app.get("/api/v1/products", response_model=list[ProductResponse])
async def products() -> list[ProductResponse]:
    return [product_response(row) for row in await store.list_products()]


@app.post("/api/v1/products", response_model=ProductResponse, status_code=202)
async def create_product(request: ProductCreateRequest) -> ProductResponse:
    try:
        product, job = await store.create_product_and_job(request.topic, request.metadata, request.idempotency_key)
        await queue.enqueue(str(job["id"]))
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return product_response(product)


@app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str) -> ProductResponse:
    row = await store.get_product(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="product not found")
    return product_response(row)


@app.post("/api/v1/radar", response_model=RadarResponse)
async def radar(request: RadarRequest) -> RadarResponse:
    result = radar_service.score(request.model_dump())
    return RadarResponse(score=result.score, confidence=result.confidence, dimensions=result.dimensions, findings=result.findings)


@app.get("/api/v1/radar", response_model=RadarResponse)
async def radar_default() -> RadarResponse:
    result = radar_service.score({})
    return RadarResponse(score=result.score, confidence=result.confidence, dimensions=result.dimensions, findings=result.findings)


@app.post("/api/v1/products/{product_id}/quality", response_model=QualityResponse)
async def quality(product_id: str, product: dict) -> QualityResponse:
    if not await store.get_product(product_id):
        raise HTTPException(status_code=404, detail="product not found")
    result = quality_service.evaluate(product)
    return QualityResponse(score=result.score, decision=result.decision, dimensions=result.dimensions, findings=result.findings, safe_fixes=result.safe_fixes)


@app.get("/api/v1/sales", response_model=SalesSummary)
async def sales(range_start: date | None = None, range_end: date | None = None) -> SalesSummary:
    return SalesSummary(**sales_service.summary(range_start, range_end))


@app.get("/api/v1/analytics", response_model=AnalyticsResponse)
async def analytics(range_start: date | None = None, range_end: date | None = None) -> AnalyticsResponse:
    return AnalyticsResponse(**analytics_service.insights(range_start, range_end))


@app.get("/api/v1/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    products_list = await store.list_products()
    jobs_list = await store.list_jobs()
    return DashboardResponse(products=len(products_list), active_jobs=sum(row["status"] in {"pending", "running", "retrying"} for row in jobs_list), completed_products=sum(row["status"] == "completed" for row in products_list), revenue=None, sales=None, integrations=integration_service.status())
