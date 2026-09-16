import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .ai_gateway.factory import build_ai_gateway
from .ai_gateway.unavailable import UnavailableAIGateway
from .agents.autonomous import AGENT_NAMES, CommerceAgent
from .agents.diagnostic import DiagnosticAgent
from .agents.registry import AgentRegistry
from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .integrations.hotmart_routes import build_hotmart_router
from .queue import JobQueue
from .schemas import *
from .services.analytics import AnalyticsService
from .services.autonomous_cycle import discover_public_signals
from .services.chat_commands import handle_chat_command
from .services.commerce_routes import build_commerce_router
from .services.commerce_store import CommerceStore
from .services.controls import ControlService
from .services.integrations import integration_service
from .services.orchestrator import AutonomousOrchestrator
from .services.persistence import PersistentStore
from .services.quality import quality_service
from .services.radar import radar_service
from .services.sales import SalesService
from .services.studio import build_studio_router
from .worker_runtime import run_worker_cycle
from worker.main import process_product, recover_pending

settings = get_settings()
ai_gateway = build_ai_gateway(settings) if settings.ai_configured else UnavailableAIGateway()
registry = AgentRegistry()
db = SupabaseREST(settings)
store = PersistentStore(db)
commerce = CommerceStore(db)
controls = ControlService()
queue = JobQueue(settings.redis_url, db)
sales_service = SalesService(db)
analytics_service = AnalyticsService(db)
orchestrator = AutonomousOrchestrator(commerce, store, queue, controls)

async def autonomous_loop() -> None:
    while True:
        try:
            status = controls.get_status()
            if not status.get("kill_switches", {}).get("global") and not status.get("settings", {}).get("pause_radar"):
                await discover_public_signals(commerce, limit=8)
                await orchestrator.run_cycle(limit=3)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(900)

async def embedded_worker() -> None:
    while True:
        try:
            await recover_pending(store, queue)
            while True:
                await run_worker_cycle(store, queue, process_product)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(15)

@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.register(DiagnosticAgent(ai_gateway))
    for agent_name in AGENT_NAMES:
        registry.register(CommerceAgent(agent_name, ai_gateway))
    worker_task = asyncio.create_task(embedded_worker(), name="hermes-embedded-worker")
    autonomous_task = asyncio.create_task(autonomous_loop(), name="hermes-autonomous-loop")
    try:
        yield
    finally:
        worker_task.cancel()
        autonomous_task.cancel()
        for task in (worker_task, autonomous_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        await queue.close()

app = FastAPI(title=settings.app_name, version="0.7.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(build_studio_router(store, db))
app.include_router(build_hotmart_router(store))
app.include_router(build_commerce_router(store, commerce, controls))

def product_response(row: dict) -> ProductResponse:
    from .product_factory import PIPELINE_STAGES
    metadata = dict(row.get("metadata") or {})
    metadata["job_id"] = row.get("job_id")
    return ProductResponse(id=str(row["id"]), topic=row["topic"], title=row.get("title"), status=row["status"], current_stage=row["current_stage"], stages=list(PIPELINE_STAGES), metadata=metadata, created_at=row["created_at"])

def job_response(row: dict) -> JobResponse:
    return JobResponse(id=str(row["id"]), job_type=row["job_type"], status=row["status"], attempts=row["attempts"], max_attempts=row["max_attempts"], error_message=row.get("error_message"), payload=row.get("payload") or {}, created_at=row["created_at"])

@app.get("/")
@app.head("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "hermes-pro-api", "version": app.version}

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="hermes-pro-api", environment=settings.app_env)

@app.get("/api/v1/system/status")
async def system_status() -> dict[str, object]:
    supabase_ok = await db.health() if settings.supabase_url and settings.supabase_secret_key else False
    return {
        "api": True,
        "ai": settings.ai_configured,
        "ai_provider": settings.effective_ai_provider,
        "supabase": supabase_ok,
        "queue": "redis" if queue.uses_redis else ("supabase" if settings.supabase_url and settings.supabase_secret_key else "unconfigured"),
        "hotmart_credentials": bool(settings.hotmart_client_id and settings.hotmart_client_secret),
        "telegram_credentials": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }

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
    try:
        command_result = await handle_chat_command(request.message, store, queue)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail=f"Persistência Supabase indisponível: {exc}") from exc
    if command_result:
        return ChatResponse(**command_result)
    now = datetime.now().astimezone()
    temporal_context = now.strftime("%Y-%m-%d %H:%M:%S %Z (weekday=%A)")
    try:
        result = await ai_gateway.complete(request.message, system=(
            "You are Hermes Pro, an autonomous commerce operations assistant. "
            "Be concise, truthful, and never invent sales, integrations, publication, or completed jobs. "
            f"The current server date and time is {temporal_context}. "
            "Use server time when asked for current time."
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

@app.post("/api/v1/opportunities", response_model=OpportunityResponse, status_code=201)
async def create_opportunity(request: OpportunityCreateRequest) -> OpportunityResponse:
    try:
        row = await commerce.create_opportunity(request.model_dump(exclude_none=True), request.idempotency_key)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de oportunidades indisponível.") from exc
    return OpportunityResponse(**row)

@app.get("/api/v1/opportunities", response_model=list[OpportunityResponse])
async def opportunities() -> list[OpportunityResponse]:
    try:
        rows = await commerce.list_opportunities()
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de oportunidades indisponível.") from exc
    return [OpportunityResponse(**row) for row in rows]

@app.get("/api/v1/events")
async def events() -> list[dict]:
    try:
        return await commerce.list_events()
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de eventos indisponível.") from exc

@app.get("/api/v1/expenses")
async def expenses() -> list[dict]:
    try:
        return await commerce.list_expenses()
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência de custos indisponível.") from exc

@app.get("/api/v1/controls")
async def get_controls() -> dict[str, object]:
    return controls.get_status()

@app.post("/api/v1/controls/kill-switch", status_code=200)
async def set_control(request: ControlRequest) -> dict[str, object]:
    controls.set_kill_switch(request.name, request.enabled)
    return controls.get_status()

@app.post("/api/v1/products/{product_id}/quality", response_model=QualityResponse)
async def quality(product_id: str, product: dict) -> QualityResponse:
    try:
        row = await store.get_product(product_id)
    except SupabaseError as exc:
        raise HTTPException(status_code=503, detail="Persistência Supabase não configurada.") from exc
    if not row:
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
    except SupabaseError:
        products_list, jobs_list = [], []
        sales_data = {"revenue": None, "orders": None}
    return DashboardResponse(
        products=len(products_list),
        active_jobs=sum(row["status"] in {"pending", "running", "retrying"} for row in jobs_list),
        completed_products=sum(row["status"] in {"completed", "content_ready", "ready_to_sell"} for row in products_list),
        revenue=sales_data.get("revenue"),
        sales=sales_data.get("orders"),
        integrations=integration_service.status(),
    )
