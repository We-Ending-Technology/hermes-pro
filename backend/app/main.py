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
            settings_state = status.get("settings") or {}
            if not status.get("kill_switches", {}).get("global") and not settings_state.get("pause_radar"):
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
