import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from uuid import uuid4

import hmac

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .ai_gateway.factory import build_ai_gateway
from .agents.diagnostic import DiagnosticAgent
from .agents.registry import AgentRegistry
from .agents.stubs import AGENT_NAMES, PassThroughAgent
from .api_commercial import router as commercial_router
from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .queue import JobQueue
from .schemas import *
from .schemas_ext import KiwifyPublicationRequest, ProductUpdateRequest
from .services.analytics import analytics_service
from .services.autonomy import AutonomyService
from .services.integrations import integration_service
from .services.persistence import PersistentStore
from .services.quality import quality_service
from .services.radar import radar_service
from .services.sales import SalesService

logger = logging.getLogger("hermes.api")
settings = get_settings()
ai_gateway = build_ai_gateway(settings)
registry = AgentRegistry()
db = SupabaseREST(settings)
store = PersistentStore(db)
sales_service = SalesService(db)
queue = JobQueue(settings.redis_url or "redis://localhost:6379/0")
autonomy = AutonomyService(settings, store)


async def _run_embedded_worker() -> None:
    """Run the queue consumer inside the free API service when no paid worker exists."""
    from worker.main import run as run_worker

    while True:
        try:
            await run_worker()
            logger.warning("embedded worker exited; retrying in 60 seconds")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("embedded worker stopped unexpectedly; retrying in 60 seconds")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.register(DiagnosticAgent(ai_gateway))
    for agent_name in AGENT_NAMES:
        registry.register(PassThroughAgent(agent_name))

    worker_task = None
    if settings.embedded_worker_enabled:
        worker_task = asyncio.create_task(_run_embedded_worker(), name="hermes-embedded-worker")
        logger.info("embedded worker enabled")
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        await queue.close()


app = FastAPI(title=settings.app_name, version="0.5.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def require_private_api_key(request: Request, call_next):
    public_paths = {"/", "/health", "/ready", "/api/v1/webhooks/hotmart", "/api/v1/webhooks/kiwify"}
    if request.method == "OPTIONS" or request.url.path in public_paths:
        return await call_next(request)
    if not settings.hermes_api_key:
        return JSONResponse({"detail": "Private API access is not configured."}, status_code=503)
    supplied = request.headers.get("X-Hermes-API-Key", "")
    if not hmac.compare_digest(supplied, settings.hermes_api_key):
        return JSONResponse({"detail": "Acesso privado: chave inválida ou ausente."}, status_code=401)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.vercel\.app$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(commercial_router)


def product_response(row: dict) -> ProductResponse:
    metadata = dict(row.get("metadata") or {})
    metadata["job_id"] = row.get("job_id")
    metadata["paused"] = bool(row.get("paused", False))
    return ProductResponse(id=str(row["id"]), topic=row["topic"], title=row.get("title"), status=row["status"], current_stage=row["current_stage"], stages=list(__import__("backend.app.product_factory", fromlist=["PIPELINE_STAGES"]).PIPELINE_STAGES), metadata=metadata, created_at=row["created_at"])


def job_response(row: dict) -> JobResponse:
    return JobResponse(id=str(row["id"]), job_type=row["job_type"], status=row["status"], attempts=row["attempts"], max_attempts=row["max_attempts"], error_message=row.get("error_message"), payload=row.get("payload") or {}, created_at=row["created_at"])


@app.get("/")
async def root(): return {"status":"ok","service":"hermes-pro-api","version":"0.5.0"}


@app.get("/health", response_model=HealthResponse)
async def health(): return HealthResponse(status="ok", service="hermes-pro-api", environment=settings.app_env)


@app.get("/ready")
async def readiness():
    """Readiness probe: confirm the API process and its Supabase data path are usable."""
    try:
        database_ready = await db.health()
    except Exception:
        logger.exception("readiness database probe raised an unexpected exception")
        database_ready = False

    checked_at = datetime.now().astimezone().isoformat()
    if not database_ready:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "hermes-pro-api",
                "checks": {"api": "ok", "database": "error"},
                "checked_at": checked_at,
            },
        )
    return {
        "status": "ready",
        "service": "hermes-pro-api",
        "checks": {"api": "ok", "database": "ok"},
        "checked_at": checked_at,
    }


@app.get("/api/v1/agents")
async def list_agents(): return {"agents": registry.names()}


@app.get("/api/v1/agents/status")
async def agents_status():
    provider = settings.ai_provider.strip().lower()
    if provider == "gemini":
        ready = bool(settings.gemini_api_key or settings.ai_api_key)
        blocked_reason = "blocked_missing_GEMINI_API_KEY"
    elif provider == "openai":
        ready = bool(settings.openai_api_key)
        blocked_reason = "blocked_missing_OPENAI_API_KEY"
    else:
        ready = False
        blocked_reason = "blocked_non_production_AI_PROVIDER"
    return {
        "chief": "ready" if ready else blocked_reason,
        "agents": [
            {"name": "Hermes Chefe", "role": "orchestrator", "status": "ready" if ready else "blocked"},
            {"name": "Hermes Radar", "role": "research", "status": "ready" if ready else "blocked"},
            {"name": "Hermes Factory", "role": "product", "status": "ready" if ready else "blocked"},
            {"name": "Hermes Dev", "role": "engineering", "status": "ready" if ready else "blocked"},
            {"name": "Hermes Analyst", "role": "analysis", "status": "ready" if ready else "blocked"},
        ],
        "autonomy_enabled": settings.autonomy_enabled,
        "embedded_worker_enabled": settings.embedded_worker_enabled,
    }


@app.get("/api/v1/agents/runs")
async def agent_runs():
    return {"runs": await store.list_agent_runs()}


@app.post("/api/v1/agents/dispatch")
async def dispatch_agent(request: AgentRunRequest):
    prompt = str(request.input.get("prompt", request.input))
    job = await autonomy.create_job(f"Execute this Hermes task autonomously: {prompt}", source="api")
    await queue.enqueue_agent(str(job["id"]))
    return {"run_id": str(job["id"]), "agent": "Hermes Chefe", "status": "queued", "output": {}}


@app.post("/api/v1/agents/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest):
    try: agent = registry.get(request.agent)
    except KeyError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    output = await agent.run(request.input)
    return AgentRunResponse(run_id=str(uuid4()), agent=request.agent, status="completed", output=output)


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    now = datetime.now().astimezone()
    temporal_context = now.strftime("%Y-%m-%d %H:%M:%S %Z (weekday=%A)")
    result = await ai_gateway.complete(
        request.message,
        system=(
            "You are Hermes Pro, an operations assistant for digital products. "
            "Be concise, truthful, and never invent sales, integrations, or completed jobs. "
            f"The current server date and time is {temporal_context}. "
            "When asked for the current date or time, use this value and state that it is server time."
        ),
    )
    return ChatResponse(response=result.content, provider=result.provider, model=result.model)


@app.get("/api/v1/integrations", response_model=list[IntegrationStatus])
async def integrations(): return [IntegrationStatus(**item) for item in integration_service.status()]


@app.get("/api/v1/jobs", response_model=list[JobResponse])
async def jobs(): return [job_response(row) for row in await store.list_jobs()]


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    row = await store.get_job(job_id)
    if not row: raise HTTPException(status_code=404, detail="job not found")
    return job_response(row)


@app.post("/api/v1/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str):
    job = await store.get_job(job_id)
    if not job: raise HTTPException(status_code=404, detail="job not found")
    if job["status"] in {"completed", "failed", "cancelled"}: return job_response(job)
    updated = await store.update_job(job_id, "cancelled", error_message="cancelled by operator")
    product_id = (job.get("payload") or {}).get("product_id")
    if product_id: await store.update_product(product_id, status="cancelled")
    return job_response(updated)


@app.get("/api/v1/products", response_model=list[ProductResponse])
async def products(): return [product_response(row) for row in await store.list_products()]


@app.post("/api/v1/products", response_model=ProductResponse, status_code=202)
async def create_product(request: ProductCreateRequest):
    try:
        product, job = await store.create_product_and_job(request.topic, request.metadata, request.idempotency_key)
        await queue.enqueue(str(job["id"]))
    except SupabaseError as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
    return product_response(product)


@app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    return product_response(row)


@app.post("/api/v1/products/{product_id}/publication/kiwify", response_model=ProductResponse)
async def save_kiwify_publication(product_id: str, request: KiwifyPublicationRequest):
    row = await store.get_product(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="product not found")
    if row.get("status") != "completed":
        raise HTTPException(status_code=409, detail="only completed products can be linked to a checkout")

    metadata = dict(row.get("metadata") or {})
    publications = dict(metadata.get("publications") or {})
    publications["kiwify"] = {
        "product_id": request.product_id,
        "checkout_url": str(request.checkout_url),
        "status": "checkout_configured",
        "verified": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata["publications"] = publications
    updated = await store.update_product(product_id, metadata=metadata)
    return product_response(updated)


@app.patch("/api/v1/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, request: ProductUpdateRequest):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    if row["status"] in {"completed", "cancelled"}: raise HTTPException(status_code=409, detail="product is not editable in its current state")
    updated = await store.update_product(product_id, title=request.title, metadata=request.metadata)
    return product_response(updated)


@app.post("/api/v1/products/{product_id}/pause", response_model=ProductResponse)
async def pause_product(product_id: str):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    metadata = dict(row.get("metadata") or {}); metadata["paused"] = True
    updated = await store.update_product(product_id, status="paused", metadata=metadata)
    if row.get("job_id"): await store.update_job(str(row["job_id"]), "paused", error_message="paused by operator")
    return product_response(updated)


@app.post("/api/v1/products/{product_id}/resume", response_model=ProductResponse)
async def resume_product(product_id: str):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    metadata = dict(row.get("metadata") or {}); metadata["paused"] = False
    updated = await store.update_product(product_id, status="queued", metadata=metadata)
    if row.get("job_id"):
        await store.update_job(str(row["job_id"]), "pending", error_message=None)
        await queue.enqueue(str(row["job_id"]))
    return product_response(updated)


@app.post("/api/v1/radar", response_model=RadarResponse)
async def radar(request: RadarRequest):
    result = radar_service.score(request.model_dump())
    return RadarResponse(score=result.score, confidence=result.confidence, dimensions=result.dimensions, findings=result.findings)


@app.get("/api/v1/radar", response_model=RadarResponse)
async def radar_default():
    result = radar_service.score({})
    return RadarResponse(score=result.score, confidence=result.confidence, dimensions=result.dimensions, findings=result.findings)


@app.post("/api/v1/products/{product_id}/quality", response_model=QualityResponse)
async def quality(product_id: str, product: dict):
    if not await store.get_product(product_id): raise HTTPException(status_code=404, detail="product not found")
    result = quality_service.evaluate(product)
    return QualityResponse(score=result.score, decision=result.decision, dimensions=result.dimensions, findings=result.findings, safe_fixes=result.safe_fixes)


@app.get("/api/v1/sales", response_model=SalesSummary)
async def sales(range_start: date | None = None, range_end: date | None = None): return SalesSummary(**(await sales_service.summary(range_start, range_end)))


@app.get("/api/v1/analytics", response_model=AnalyticsResponse)
async def analytics(range_start: date | None = None, range_end: date | None = None): return AnalyticsResponse(**analytics_service.insights(range_start, range_end))


@app.get("/api/v1/dashboard", response_model=DashboardResponse)
async def dashboard():
    products_list = await store.list_products(); jobs_list = await store.list_jobs()
    sales_data = await sales_service.summary()
    return DashboardResponse(products=len(products_list), active_jobs=sum(row["status"] in {"pending","running","retrying"} for row in jobs_list), completed_products=sum(row["status"] in {"completed"} for row in products_list), revenue=sales_data.get("revenue"), sales=sales_data.get("orders"), integrations=integration_service.status())
