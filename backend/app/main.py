from contextlib import asynccontextmanager
from datetime import date, datetime
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
from .services.analytics import AnalyticsService
from .services.controls import ControlService
from .services.integrations import integration_service
from .services.opportunities import OpportunityService
from .services.persistence import PersistentStore
from .services.quality import quality_service
from .services.radar import radar_service
from .services.sales import SalesService
from .services.service_opportunities import ServiceOpportunityService

settings = get_settings()
ai_gateway = build_ai_gateway(settings)
registry = AgentRegistry()
db = SupabaseREST(settings)
store = PersistentStore(db)
queue = JobQueue(settings.redis_url)
sales_service = SalesService(db)
analytics_service = AnalyticsService(db)
opportunity_service = OpportunityService(db)
service_opportunity_service = ServiceOpportunityService(db)
control_service = ControlService(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.register(DiagnosticAgent(ai_gateway))
    for agent_name in AGENT_NAMES:
        registry.register(PassThroughAgent(agent_name))
    yield
    await queue.close()


app = FastAPI(title=settings.app_name, version="0.5.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def product_response(row: dict) -> ProductResponse:
    from .product_factory import PIPELINE_STAGES
    metadata = dict(row.get("metadata") or {})
    metadata["job_id"] = row.get("job_id")
    return ProductResponse(id=str(row["id"]), topic=row["topic"], title=row.get("title"), status=row["status"], current_stage=row["current_stage"], stages=list(PIPELINE_STAGES), metadata=metadata, created_at=row["created_at"])


def job_response(row: dict) -> JobResponse:
    return JobResponse(id=str(row["id"]), job_type=row["job_type"], status=row["status"], attempts=row["attempts"], max_attempts=row["max_attempts"], error_message=row.get("error_message"), payload=row.get("payload") or {}, created_at=row["created_at"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "hermes-pro-api", "version": app.version}


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
    now = datetime.now().astimezone()
    temporal_context = now.strftime("%Y-%m-%d %H:%M:%S %Z (weekday=%A)")
    try:
        result = await ai_gateway.complete(request.message, system=(
            "You are Hermes Pro, an autonomous commerce operations assistant. "
            "Be concise, truthful, and never invent sales, integrations, market data, or completed jobs. "
            f"The current server date and time is {temporal_context}. "
            "When asked for the current date or time, use this value and state that it is server time."
        ))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI Gateway indisponível: {exc}") from exc
    return ChatResponse(response=result.content, provider=result.provider, model=result.model)


@app.get("/api/v1/integrations", response_model=list[IntegrationStatus])
async def integrations() -> list[IntegrationStatus]:
    return [IntegrationStatus(**item) for item in integration_service.status()]


@app.get("/api/v1/jobs", response_model=list[JobResponse])
async def jobs() -> list[JobResponse]:
    try:
        rows = await store.list_jobs()
    except SupabaseError:
        return []
    return [job_response(row) for row in rows]


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    try:
        row = await store.get_job(job_id)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência Supabase não configurada.") from exc
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    return job_response(row)


@app.get("/api/v1/products", response_model=list[ProductResponse])
async def products() -> list[ProductResponse]:
    try:
        rows = await store.list_products()
    except SupabaseError:
        return []
    return [product_response(row) for row in rows]


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
    try:
        row = await store.get_product(product_id)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência Supabase não configurada.") from exc
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


@app.get("/api/v1/opportunities", response_model=list[OpportunityResponse])
async def opportunities(limit: int = 50) -> list[OpportunityResponse]:
    try:
        rows = await opportunity_service.list(max(1, min(limit, 100)))
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de oportunidades indisponível.") from exc
    return [OpportunityResponse(**row) for row in rows]


@app.post("/api/v1/opportunities", response_model=OpportunityResponse, status_code=201)
async def create_opportunity(request: OpportunityCreateRequest) -> OpportunityResponse:
    try:
        row = await opportunity_service.create(request.model_dump())
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return OpportunityResponse(**row)


@app.post("/api/v1/opportunities/{opportunity_id}/score")
async def score_opportunity(opportunity_id: str) -> dict:
    try:
        return await opportunity_service.score(opportunity_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="opportunity not found") from exc
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/services", response_model=list[ServiceResponse])
async def services(limit: int = 50) -> list[ServiceResponse]:
    try:
        rows = await service_opportunity_service.list(max(1, min(limit, 100)))
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de serviços indisponível.") from exc
    return [ServiceResponse(**row) for row in rows]


@app.post("/api/v1/services", response_model=ServiceResponse, status_code=201)
async def create_service(request: ServiceCreateRequest) -> ServiceResponse:
    try:
        row = await service_opportunity_service.create(request.model_dump())
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ServiceResponse(**row)


@app.get("/api/v1/controls", response_model=ControlResponse)
async def controls() -> ControlResponse:
    try:
        return ControlResponse(**await control_service.get())
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de controles indisponível.") from exc


@app.put("/api/v1/controls", response_model=ControlResponse)
async def update_controls(request: ControlUpdateRequest) -> ControlResponse:
    try:
        payload = {key: value for key, value in request.model_dump().items() if value is not None}
        return ControlResponse(**await control_service.update(payload))
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Não foi possível atualizar os controles.") from exc


@app.post("/api/v1/events", response_model=EventResponse, status_code=201)
async def create_event(request: EventCreateRequest) -> EventResponse:
    try:
        if request.idempotency_key:
            existing = await db.select("hermes_events", params={"select": "*", "idempotency_key": f"eq.{request.idempotency_key}", "limit": "1"})
            if existing:
                return EventResponse(**existing[0])
        row = await db.insert("hermes_events", request.model_dump())
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de eventos indisponível.") from exc
    return EventResponse(**row)


@app.post("/api/v1/products/{product_id}/quality", response_model=QualityResponse)
async def quality(product_id: str, product: dict) -> QualityResponse:
    if not await store.get_product(product_id):
        raise HTTPException(status_code=404, detail="product not found")
    result = quality_service.evaluate(product)
    return QualityResponse(score=result.score, decision=result.decision, dimensions=result.dimensions, findings=result.findings, safe_fixes=result.safe_fixes)


@app.get("/api/v1/sales", response_model=SalesSummary)
async def sales(range_start: date | None = None, range_end: date | None = None) -> SalesSummary:
    try:
        return SalesSummary(**await sales_service.summary(range_start, range_end))
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de vendas indisponível.") from exc


@app.get("/api/v1/analytics", response_model=AnalyticsResponse)
async def analytics(range_start: date | None = None, range_end: date | None = None) -> AnalyticsResponse:
    try:
        return AnalyticsResponse(**await analytics_service.insights(range_start, range_end))
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de analytics indisponível.") from exc


@app.get("/api/v1/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    try:
        products_list = await store.list_products()
        jobs_list = await store.list_jobs()
        sales_data = await sales_service.summary()
        expenses = await db.select("hermes_expenses", params={"select": "category,amount"})
    except SupabaseError:
        products_list, jobs_list = [], []
        sales_data = {"revenue": None, "orders": None}
        expenses = []
    costs = {"ai": 0.0, "infra": 0.0, "ads": 0.0, "other": 0.0}
    for expense in expenses:
        category = str(expense.get("category", "other"))
        if category in costs:
            costs[category] += float(expense.get("amount") or 0)
    revenue = sales_data.get("revenue")
    operating_profit = None if revenue is None else round(float(revenue) - sum(costs.values()), 2)
    return DashboardResponse(
        products=len(products_list),
        active_jobs=sum(row["status"] in {"pending", "running", "retrying"} for row in jobs_list),
        completed_products=sum(row["status"] in {"completed", "content_ready", "ready_to_sell"} for row in products_list),
        revenue=revenue,
        sales=sales_data.get("orders"),
        operating_profit=operating_profit,
        integrations=integration_service.status(),
    )
