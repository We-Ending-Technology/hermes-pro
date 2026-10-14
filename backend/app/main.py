from contextlib import asynccontextmanager
import asyncio
import logging
import secrets
from datetime import date, datetime
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .ai_gateway.factory import build_ai_gateway
from .agents.diagnostic import DiagnosticAgent
from .agents.agents_sdk import run_chief
from .agents.registry import AgentRegistry
from .agents.stubs import AGENT_NAMES, PassThroughAgent
from .agents.operational import (RadarAgent, ResearcherAgent, AnalystAgent, ExecutorAgent, QAAgent, CommercialAgent, FinanceAgent, RecoveryAgent, GuardianAgent, WatchtowerAgent, SupervisorAgent)
from .services.autonomy import AutonomyService
from .api_commercial import router as commercial_router
from .api_autonomy import router as autonomy_router
from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .queue import JobQueue
from .schemas import *
from .schemas_ext import ProductUpdateRequest
from .services.analytics import analytics_service
from .services.integrations import integration_service
from .services.persistence import PersistentStore
from .services.quality import quality_service
from .services.radar import radar_service
from .services.sales import SalesService

settings = get_settings()
ai_gateway = build_ai_gateway(settings)
registry = AgentRegistry()
db = SupabaseREST(settings)
store = PersistentStore(db)
sales_service = SalesService(db)
queue = JobQueue(settings.redis_url)
autonomy_service = AutonomyService(store, queue)
autonomy_lock = asyncio.Lock()
logger = logging.getLogger("hermes.api.autonomy")


class InlineOpportunityQueue:
    async def enqueue(self, job_id: str) -> None:
        # Retries are driven by the bounded inline loop, not a missing worker.
        return None


async def _process_pending_opportunities() -> list[dict]:
    from worker.main import MAX_ATTEMPTS, process_opportunity

    processed = []
    jobs = await store.list_jobs()
    for job in jobs:
        if job.get("job_type") != "opportunity_pipeline" or job.get("status") not in {"pending", "retrying"}:
            continue
        job_id = str(job["id"])
        for _ in range(MAX_ATTEMPTS):
            current = await store.get_job(job_id)
            if not current or current.get("status") not in {"pending", "retrying"}:
                break
            await process_opportunity(job_id, store, InlineOpportunityQueue())
            current = await store.get_job(job_id)
            if not current or current.get("status") != "retrying":
                break
        final = await store.get_job(job_id)
        processed.append({"job_id": job_id, "status": final.get("status") if final else "missing"})
    return processed


async def _run_autonomy_once() -> dict:
    async with autonomy_lock:
        cycle = await autonomy_service.cycle(settings.autonomy_min_score, enqueue_jobs=False)
        processed = await _process_pending_opportunities()
        return {**cycle, "processed_jobs": processed, "scheduler_mode": "inline_api_process"}


async def _autonomy_loop() -> None:
    interval = max(60, int(settings.autonomy_interval_seconds))
    while True:
        try:
            if settings.autonomy_enabled:
                result = await _run_autonomy_once()
                logger.info(
                    "autonomy cycle completed scanned=%s queued=%s processed=%s",
                    result.get("scanned", 0), result.get("queued", 0), len(result.get("processed_jobs", [])),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("autonomy cycle failed; will retry next interval")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.register(DiagnosticAgent(ai_gateway))
    operational = [
        RadarAgent(), ResearcherAgent(), AnalystAgent(), ExecutorAgent(), QAAgent(),
        CommercialAgent(ai_gateway), FinanceAgent(), RecoveryAgent(), GuardianAgent(),
        WatchtowerAgent(), SupervisorAgent(),
    ]
    for agent in operational:
        registry.register(agent)
    mapped = {agent.name for agent in operational} | {"diagnostic"}
    for agent_name in AGENT_NAMES:
        if agent_name not in mapped:
            registry.register(PassThroughAgent(agent_name))
    scheduler_enabled = settings.autonomy_enabled and settings.app_env.strip().lower() == "production"
    scheduler_task = asyncio.create_task(_autonomy_loop(), name="hermes-autonomy-loop") if scheduler_enabled else None
    app.state.autonomy_scheduler_mode = "inline_api_process" if scheduler_task else "disabled"
    try:
        yield
    finally:
        if scheduler_task:
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        await queue.close()

app = FastAPI(title=settings.app_name, version="0.5.0", lifespan=lifespan)
app.include_router(commercial_router)
app.include_router(autonomy_router)

@app.middleware("http")
async def require_admin_api_token(request: Request, call_next):
    path = request.url.path
    # Health/readiness stay public for hosting probes. Hotmart webhooks use their own token.
    # These scheduler-only routes validate X-Hermes-Scheduler themselves.
    # Do not force the browser/admin token on machine-to-machine scheduler calls.
    scheduler_route = (
        path == "/api/v1/autonomy/freelancer/sync"
        or path.startswith("/api/v1/autonomy/freelancer/apply/")
        or (path.startswith("/api/v1/autonomy/jobs/") and path.endswith("/execute"))
    )
    # Public read-only dashboard endpoints do not need a browser-held secret.
    # AI execution, chat, mutations, and financial actions remain protected.
    public_read_routes = {
        "/api/v1/dashboard",
        "/api/v1/jobs",
        "/api/v1/products",
        "/api/v1/integrations",
        "/api/v1/agents",
        "/api/v1/agents/status",
        "/api/v1/agents/runs",
        "/ready",
    }
    public_read = request.method == "GET" and path in public_read_routes
    if path.startswith("/api/v1/") and path != "/api/v1/webhooks/hotmart" and not scheduler_route and not public_read:
        expected = settings.hermes_api_token
        supplied = request.headers.get("X-Hermes-API-Key", "")
        if not expected:
            return JSONResponse(status_code=503, content={"detail": "API authentication is not configured"})
        if not supplied or not secrets.compare_digest(supplied, expected):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    return await call_next(request)

# CORS must wrap authentication so browser clients receive CORS headers on 401/503 responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.vercel\.app$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/api/v1/agents")
async def list_agents(): return {"agents": registry.names()}

@app.get("/api/v1/agents/status")
async def agents_status():
    # A configured key or a registered class is not proof that an agent has
    # completed a successful real-world run. Report configuration and handler
    # presence separately so the dashboard cannot label placeholders as ready.
    provider = (settings.ai_provider or "").strip().lower()
    if provider == "openai":
        ai_configured = bool(settings.openai_api_key)
    elif provider == "gemini":
        ai_configured = bool(settings.gemini_api_key)
    elif provider in {"stub", "mock"}:
        ai_configured = False
    else:
        ai_configured = bool(settings.ai_api_key or settings.openai_api_key or settings.gemini_api_key)

    agents = []
    for name in registry.names():
        agent = registry.get(name)
        placeholder = isinstance(agent, PassThroughAgent)
        agents.append({
            "name": name,
            "handler": type(agent).__name__,
            "status": "placeholder" if placeholder else "registered_unverified",
            "execution_verified": False,
        })

    return {
        "chief": "configured_unverified" if ai_configured else "blocked_missing_provider_credentials",
        "autonomy_enabled": settings.autonomy_enabled,
        "overall": "configuration_incomplete" if not (ai_configured and settings.supabase_url and settings.supabase_secret_key) else "configured_unverified",
        "dependencies": {
            "ai_provider": provider or "unset",
            "ai_credentials_configured": ai_configured,
            "supabase_configured": bool(settings.supabase_url and settings.supabase_secret_key),
            "redis_url_configured": bool(settings.redis_url),
            "freelancer_enabled": settings.freelancer_enabled,
            "freelancer_auto_apply_enabled": settings.freelancer_auto_apply,
        },
        "agents": agents,
        "note": "Registered/configured does not mean a successful execution was verified. Run a real test job to establish execution evidence.",
    }

@app.get("/api/v1/agents/runs")
async def agent_runs():
    return {"runs": await store.list_agent_runs()}

@app.post("/api/v1/agents/dispatch")
async def dispatch_agent(request: AgentRunRequest):
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    prompt = str(request.input.get("prompt", request.input))
    result = await run_chief(prompt, request.input)
    return {"run_id": str(uuid4()), "agent": result["last_agent"], "status": "completed", "output": result}

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

@app.post("/api/v1/autonomy/cycle")
async def autonomy_cycle():
    if not settings.autonomy_enabled:
        raise HTTPException(status_code=409, detail="autonomy disabled")
    return await _run_autonomy_once()

@app.get("/api/v1/autonomy/status")
async def autonomy_status():
    return {
        "enabled": settings.autonomy_enabled,
        "minimum_score": settings.autonomy_min_score,
        "agents": registry.names(),
        "runtime": {
            "mode": getattr(app.state, "autonomy_scheduler_mode", "unknown"),
            "interval_seconds": max(60, int(settings.autonomy_interval_seconds)),
            "continuous_24_7_guaranteed": False,
            "note": "Inline scheduling runs while this API process is awake; a free hosting instance may sleep while idle.",
        },
    }

@app.get("/api/v1/opportunities")
async def opportunities(limit: int = 20):
    """Return saved freelance opportunities, not internal queue jobs."""
    safe_limit = min(max(limit, 1), 100)
    freelancer_rows = await db.select(
        "hermes_opportunities",
        params={"select": "*", "source": "ilike.*freelancer*", "order": "score.desc,created_at.desc", "limit": str(safe_limit)},
    )
    local_rows = await db.select(
        "hermes_opportunities",
        params={"select": "*", "source": "ilike.*99freelas*", "order": "score.desc,created_at.desc", "limit": str(safe_limit)},
    )
    rows = {str(row.get("id")): row for row in [*freelancer_rows, *local_rows]}
    relevant_terms = ("python", "api", "automation", "automação", "scrap", "excel", "csv", "pdf", "data", "dados", "backend", "integração", "integration", "bot")
    ranked = []
    for row in rows.values():
        text = " ".join(str(row.get(key) or "") for key in ("title", "description", "summary", "proposal")).lower()
        if not any(term in text for term in relevant_terms):
            continue
        row["_relevance"] = sum(1 for term in relevant_terms if term in text)
        ranked.append(row)
    ranked.sort(key=lambda row: (row["_relevance"], float(row.get("score") or 0)), reverse=True)
    for row in ranked:
        row.pop("_relevance", None)
    return ranked[:safe_limit]


@app.post("/api/v1/opportunities/{opportunity_id}/queue")
async def queue_opportunity(opportunity_id: str):
    """Create an honest proposal draft for review; never submits it automatically."""
    rows = await db.select(
        "hermes_opportunities",
        params={"select": "*", "id": f"eq.{opportunity_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="opportunity not found")
    opportunity = rows[0]
    title = str(opportunity.get("title") or "").strip()
    description = str(opportunity.get("description") or opportunity.get("summary") or "").strip()
    url = str(opportunity.get("url") or opportunity.get("source_url") or "").strip()
    if not title or not url:
        raise HTTPException(status_code=422, detail="opportunity is missing a title or source URL")
    prompt = (
        "Prepare a truthful Portuguese freelance proposal draft for human review. "
        "Do not claim experience, credentials, completed work, or facts not provided. "
        "If the brief is too vague, explicitly ask concise clarification questions and do not invent scope. "
        "Return only the proposal text.\n"
        f"Title: {title}\nBrief: {description or '[No detailed brief was captured; ask for requirements.]'}\n"
        f"Source: {opportunity.get('source') or 'unknown'}\nURL: {url}\n"
        f"Suggested budget, if any: {opportunity.get('suggested_price') or 'not provided'} {opportunity.get('currency') or 'BRL'}"
    )
    draft = await ai_gateway.complete(
        prompt,
        system="You draft honest freelance proposals in Brazilian Portuguese. Never say an application was submitted. Keep the draft concise and tailored only to supplied facts.",
    )
    metadata = dict(opportunity.get("metadata") or {})
    metadata["proposal_draft_status"] = "needs_human_review"
    metadata["proposal_draft_model"] = draft.model
    metadata["proposal_draft_provider"] = draft.provider
    await db.update(
        "hermes_opportunities",
        {"proposal": draft.content, "status": "proposal_ready", "application_status": "draft_ready", "metadata": metadata},
        where={"id": f"eq.{opportunity_id}"},
    )
    return {
        "id": opportunity_id,
        "status": "proposal_ready",
        "application_status": "draft_ready",
        "message": "Rascunho preparado. Revise e envie manualmente pela plataforma; nada foi submetido.",
        "proposal": draft.content,
        "url": url,
    }

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

async def _run_inline_product(job_id: str) -> None:
    """Process product jobs in the API process so generation works before a separate worker is provisioned."""
    from worker.main import process_product

    class InlineRetryQueue:
        async def enqueue(self, retry_job_id: str) -> None:
            asyncio.create_task(_run_inline_product(retry_job_id))

    try:
        await process_product(job_id, store, InlineRetryQueue())
    except Exception:
        import logging
        logging.getLogger("hermes.inline_worker").exception("inline product job failed: %s", job_id)


@app.post("/api/v1/products", response_model=ProductResponse, status_code=202)
async def create_product(request: ProductCreateRequest, background_tasks: BackgroundTasks):
    try:
        product, job = await store.create_product_and_job(request.topic, request.metadata, request.idempotency_key)
        background_tasks.add_task(_run_inline_product, str(job["id"]))
    except SupabaseError as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
    return product_response(product)

@app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    return product_response(row)

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
