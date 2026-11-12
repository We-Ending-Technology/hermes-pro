import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import hmac

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .ai_gateway.factory import build_ai_gateway
from .agents.diagnostic import DiagnosticAgent
from .agents.registry import AgentRegistry
from .agents.orchestrator import SPECIALISTS
from .agents.specialist import ChiefAgent, SpecialistAgent
from .api_commercial import router as commercial_router
from .api_kiwify import router as kiwify_api_router
from .core.config import get_settings
from .db.supabase import SupabaseREST, SupabaseError
from .queue import JobQueue
from .schemas import *
from .schemas_ext import KiwifyPublicationRequest, ProductUpdateRequest, is_kiwify_publishable_product
from .services.analytics import analytics_service
from .services.autonomy import AutonomyService
from .services.integrations import integration_service
from .services.persistence import PersistentStore
from .services.quality import quality_service
from .services.radar import radar_service
from .services.sales import SalesService
from .services.storage import SupabaseStorage

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
    registry.register(ChiefAgent(settings))
    for agent_name, instructions in SPECIALISTS:
        registry.register(SpecialistAgent(agent_name, instructions, ai_gateway))

    worker_task = None
    sentinel_task = None
    if settings.embedded_worker_enabled:
        worker_task = asyncio.create_task(_run_embedded_worker(), name="hermes-embedded-worker")
        logger.info("embedded worker enabled")
    if settings.sentinel_enabled:
        from .services.sentinel import run_sentinel
        sentinel_task = asyncio.create_task(
            run_sentinel(settings, store, queue, settings.sentinel_interval_seconds),
            name="hermes-sentinel",
        )
        logger.info("Hermes Sentinel enabled")
    try:
        yield
    finally:
        for task in (sentinel_task, worker_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await queue.close()


app = FastAPI(title=settings.app_name, version="0.5.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def require_private_api_key(request: Request, call_next):
    public_paths = {"/", "/health", "/ready", "/time", "/api/v1/webhooks/hotmart", "/api/v1/webhooks/kiwify"}
    if request.method == "OPTIONS" or request.url.path in public_paths:
        return await call_next(request)
    if not settings.hermes_api_key:
        return JSONResponse({"detail": "Private API access is not configured."}, status_code=503)
    supplied = request.headers.get("X-Hermes-API-Key", "")
    expected = str(settings.hermes_api_key or "")
    try:
        valid_key = hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
    except (AttributeError, UnicodeError):
        valid_key = False
    if not supplied or not valid_key:
        return JSONResponse({"detail": "Acesso privado: chave inválida ou ausente."}, status_code=401)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://(hermes-pro-command-center\.onrender\.com|[a-zA-Z0-9-]+\.vercel\.app)$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(commercial_router)
app.include_router(kiwify_api_router)


async def product_response(row: dict) -> ProductResponse:
    metadata = dict(row.get("metadata") or {})
    artifact_paths = metadata.get("artifact_paths") or {}
    expires_at_value = metadata.get("artifact_urls_expires_at")
    expires_at = None
    if expires_at_value:
        try:
            expires_at = datetime.fromisoformat(str(expires_at_value).replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except ValueError:
            expires_at = None

    now = datetime.now(timezone.utc)
    if artifact_paths and (expires_at is None or expires_at <= now + timedelta(days=1)):
        refreshed_artifacts = dict(metadata.get("artifacts") or {})
        refreshed_any = False
        for kind, locator in artifact_paths.items():
            if not isinstance(locator, dict) or not locator.get("bucket") or not locator.get("path"):
                continue
            try:
                storage = SupabaseStorage(settings, bucket=str(locator["bucket"]))
                refreshed_artifacts[str(kind)] = await storage.create_signed_url(str(locator["path"]), expires_in=604800)
                refreshed_any = True
            except Exception:
                logger.exception("could not refresh private artifact URL product=%s kind=%s", row.get("id"), kind)
        if refreshed_any:
            metadata["artifacts"] = refreshed_artifacts
            metadata["artifact_urls_expires_at"] = (now + timedelta(days=7)).isoformat()
            try:
                row = await store.update_product(str(row["id"]), metadata=metadata)
                metadata = dict(row.get("metadata") or metadata)
            except Exception:
                logger.exception("could not persist refreshed artifact URLs product=%s", row.get("id"))

    metadata["job_id"] = row.get("job_id")
    metadata["paused"] = bool(row.get("paused", False))
    return ProductResponse(id=str(row["id"]), topic=row["topic"], title=row.get("title"), status=row["status"], current_stage=row["current_stage"], stages=list(__import__("backend.app.product_factory", fromlist=["PIPELINE_STAGES"]).PIPELINE_STAGES), metadata=metadata, created_at=row["created_at"])


def job_response(row: dict) -> JobResponse:
    return JobResponse(id=str(row["id"]), job_type=row["job_type"], status=row["status"], attempts=row["attempts"], max_attempts=row["max_attempts"], error_message=row.get("error_message"), payload=row.get("payload") or {}, created_at=row["created_at"])


@app.get("/")
async def root(): return {"status":"ok","service":"hermes-pro-api","version":"0.5.0"}

@app.get("/time")
async def server_time():
    """Expose authoritative UTC time; clients render it in America/Sao_Paulo."""
    return {"utc": datetime.now(timezone.utc).isoformat(), "timezone": "America/Sao_Paulo"}

@app.get("/api/v1/auth/verify")
async def verify_private_access():
    """Confirm the private API key without database or sales dependencies."""
    return {"authenticated": True}


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
        ai_ready = bool(settings.gemini_api_key or settings.ai_api_key)
    elif provider == "openai":
        ai_ready = bool(settings.openai_api_key)
    elif provider == "groq":
        ai_ready = bool(settings.groq_api_key)
    else:
        ai_ready = False

    fallback = settings.ai_fallback_provider.strip().lower()
    fallback_ready = (
        (fallback == "gemini" and bool(settings.gemini_api_key or settings.ai_api_key))
        or (fallback == "openai" and bool(settings.openai_api_key))
        or (fallback == "groq" and bool(settings.groq_api_key))
    )
    ai_ready = ai_ready or fallback_ready

    provider_degraded = False
    provider_last_error = None
    try:
        recent_jobs = await store.db.select(
            "hermes_jobs",
            params={"select": "status,error_message,updated_at,job_type", "or": "(status.eq.failed,status.eq.retrying)", "order": "updated_at.desc", "limit": "10"},
        )
        for failed_job in recent_jobs:
            error_text = str(failed_job.get("error_message") or "")
            lowered = error_text.casefold()
            provider_error = any(marker in lowered for marker in ("429", "500", "502", "503", "504", "quota", "rate limit", "resource exhausted", "timed out", "connection error"))
            if not provider_error:
                continue
            try:
                failed_at = datetime.fromisoformat(str(failed_job.get("updated_at")).replace("Z", "+00:00"))
                if failed_at.tzinfo is None:
                    failed_at = failed_at.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - failed_at.astimezone(timezone.utc)).total_seconds()
            except (TypeError, ValueError):
                continue
            if 0 <= age <= 3600:
                provider_degraded = True
                provider_last_error = error_text[:300]
                break
    except Exception:
        logger.exception("could not inspect recent AI provider failures")

    try:
        redis_ready = bool(await queue.redis.ping())
    except Exception:
        redis_ready = False

    worker_row = None
    try:
        rows = await store.db.select(
            "hermes_system_health",
            params={"select": "status,message,checked_at", "component": "eq.worker", "limit": "1"},
        )
        worker_row = rows[0] if rows else None
    except Exception:
        worker_row = None

    worker_age_seconds = None
    if worker_row and worker_row.get("checked_at"):
        try:
            checked_at = datetime.fromisoformat(str(worker_row["checked_at"]).replace("Z", "+00:00"))
            worker_age_seconds = max(0, (datetime.now(timezone.utc) - checked_at).total_seconds())
        except (TypeError, ValueError):
            worker_age_seconds = None
    worker_ready = bool(
        settings.embedded_worker_enabled
        and worker_row
        and worker_row.get("status") == "ok"
        and worker_age_seconds is not None
        and worker_age_seconds <= 180
    )
    # A recent transient provider error should mark the Chief degraded, but must not
    # prevent durable queueing. The worker can retry the persisted job after recovery.
    dispatch_ready = ai_ready and redis_ready and worker_ready
    ready = dispatch_ready and not provider_degraded
    if not ai_ready:
        chief_status = "blocked_ai_provider_not_configured"
    elif provider_degraded:
        chief_status = "blocked_ai_provider_recent_error"
    elif not redis_ready:
        chief_status = "blocked_redis_unavailable"
    elif not worker_ready:
        chief_status = "blocked_worker_heartbeat_missing_or_stale"
    else:
        chief_status = "ready"

    return {
        "chief": chief_status,
        "dispatch_ready": dispatch_ready,
        "agents": [
            {"name": "Hermes Chefe", "role": "orchestrator", "status": "ready" if ready else "blocked"},
            {"name": "Hermes Radar", "role": "research", "status": "ready" if ready else "blocked"},
            {"name": "Hermes Factory", "role": "product", "status": "ready" if ready else "blocked"},
            {"name": "Hermes Dev", "role": "engineering", "status": "ready" if ready else "blocked"},
            {"name": "Hermes Analyst", "role": "analysis", "status": "ready" if ready else "blocked"},
        ],
        "ai_provider": provider,
        "ai_ready": ai_ready,
        "ai_fallback_provider": fallback or None,
        "ai_fallback_ready": fallback_ready,
        "ai_provider_status": "degraded" if provider_degraded else ("ready" if ai_ready else "missing"),
        "ai_provider_last_error": provider_last_error,
        "queue_status": "ready" if redis_ready else "unavailable",
        "worker_status": "ready" if worker_ready else "unavailable",
        "worker_last_seen_at": worker_row.get("checked_at") if worker_row else None,
        "worker_age_seconds": round(worker_age_seconds) if worker_age_seconds is not None else None,
        "autonomy_enabled": settings.autonomy_enabled,
        "embedded_worker_enabled": settings.embedded_worker_enabled,
        "supervision_interval_seconds": settings.autonomy_agent_interval_seconds,
    }

@app.get("/api/v1/agents/runs")
async def agent_runs():
    return {"runs": await store.list_agent_runs()}


@app.post("/api/v1/agents/dispatch")
async def dispatch_agent(request: AgentRunRequest):
    prompt = str(request.input.get("prompt", "")).strip()
    if len(prompt) < 8:
        raise HTTPException(status_code=422, detail="A tarefa precisa ter pelo menos 8 caracteres.")
    health = await agents_status()
    if not health.get("dispatch_ready", health["chief"] == "ready"):
        raise HTTPException(status_code=503, detail={"message": "Hermes Chefe sem dependências essenciais; tarefa não foi enfileirada.", "checks": health})
    try:
        job = await autonomy.create_job(
            "Execute esta tarefa pelo time Hermes e entregue evidências e recomendações: " + prompt,
            source="api",
        )
        await queue.enqueue_agent(str(job["id"]))
    except Exception as exc:
        logger.exception("failed to dispatch Hermes Chief task")
        raise HTTPException(status_code=503, detail="Não foi possível persistir/enfileirar a tarefa.") from exc
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
async def products():
    rows = await store.list_products()
    return [await product_response(row) for row in rows]


@app.post("/api/v1/products", response_model=ProductResponse, status_code=202)
async def create_product(request: ProductCreateRequest):
    try:
        product, job = await store.create_product_and_job(request.topic, request.metadata, request.idempotency_key)
        await queue.enqueue(str(job["id"]))
    except SupabaseError as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
    return await product_response(product)


@app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    return await product_response(row)


@app.post("/api/v1/products/{product_id}/publication/kiwify", response_model=ProductResponse)
async def save_kiwify_publication(product_id: str, request: KiwifyPublicationRequest):
    row = await store.get_product(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="product not found")
    if not is_kiwify_publishable_product(row):
        raise HTTPException(
            status_code=409,
            detail="Produto bloqueado: precisa passar pelo quality gate, ter nota mínima 80 e PDF, DOCX e capa válidos antes de vincular checkout.",
        )

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
    return await product_response(updated)


@app.patch("/api/v1/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, request: ProductUpdateRequest):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    if row["status"] in {"completed", "cancelled"}: raise HTTPException(status_code=409, detail="product is not editable in its current state")
    updated = await store.update_product(product_id, title=request.title, metadata=request.metadata)
    return await product_response(updated)


@app.post("/api/v1/products/{product_id}/pause", response_model=ProductResponse)
async def pause_product(product_id: str):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    metadata = dict(row.get("metadata") or {}); metadata["paused"] = True
    updated = await store.update_product(product_id, status="paused", metadata=metadata)
    if row.get("job_id"): await store.update_job(str(row["job_id"]), "paused", error_message="paused by operator")
    return await product_response(updated)


@app.post("/api/v1/products/{product_id}/resume", response_model=ProductResponse)
async def resume_product(product_id: str):
    row = await store.get_product(product_id)
    if not row: raise HTTPException(status_code=404, detail="product not found")
    metadata = dict(row.get("metadata") or {}); metadata["paused"] = False
    updated = await store.update_product(product_id, status="queued", metadata=metadata)
    if row.get("job_id"):
        await store.update_job(str(row["job_id"]), "pending", error_message=None)
        await queue.enqueue(str(row["job_id"]))
    return await product_response(updated)


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
    return DashboardResponse(products=len(products_list), active_jobs=sum(row["status"] in {"pending","running","retrying"} for row in jobs_list), completed_products=sum(row["status"] in {"completed", "ready_to_publish"} for row in products_list), revenue=sales_data.get("revenue"), sales=sales_data.get("orders"), integrations=integration_service.status())
