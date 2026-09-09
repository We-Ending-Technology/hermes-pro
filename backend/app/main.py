from contextlib import asynccontextmanager
from datetime import date
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .schemas import *
from .ai_gateway.factory import build_ai_gateway
from .agents.registry import AgentRegistry
from .agents.diagnostic import DiagnosticAgent
from .agents.stubs import PassThroughAgent, AGENT_NAMES
from .services.jobs import job_service
from .services.products import product_service
from .services.radar import radar_service
from .services.quality import quality_service
from .services.integrations import integration_service
from .services.sales import sales_service
from .services.analytics import analytics_service
from .models.jobs import JobStatus

settings = get_settings()
registry = AgentRegistry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.register(DiagnosticAgent(build_ai_gateway(settings)))
    for agent_name in AGENT_NAMES:
        registry.register(PassThroughAgent(agent_name))
    yield

app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def product_response(product) -> ProductResponse:
    return ProductResponse(id=product.id, topic=product.topic, title=product.title, status=product.status, current_stage=product.current_stage, stages=list(__import__('backend.app.product_factory', fromlist=['PIPELINE_STAGES']).PIPELINE_STAGES), metadata={**product.metadata, "job_id": product.job_id}, created_at=product.created_at)

def job_response(job) -> JobResponse:
    return JobResponse(id=job.id, job_type=job.job_type, status=job.status.value, attempts=job.attempts, max_attempts=3, error_message=job.error_message, payload=job.payload, created_at=job.created_at)

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
    try: agent = registry.get(request.agent)
    except KeyError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    output = await agent.run(request.input)
    return AgentRunResponse(run_id=str(uuid4()), agent=request.agent, status="completed", output=output)

@app.get("/api/v1/integrations", response_model=list[IntegrationStatus])
async def integrations() -> list[IntegrationStatus]:
    return [IntegrationStatus(**item) for item in integration_service.status()]

@app.get("/api/v1/jobs", response_model=list[JobResponse])
async def jobs() -> list[JobResponse]:
    return [job_response(job) for job in job_service.list()]

@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    try: return job_response(job_service.get(job_id))
    except KeyError as exc: raise HTTPException(status_code=404, detail="job not found") from exc

@app.get("/api/v1/products", response_model=list[ProductResponse])
async def products() -> list[ProductResponse]:
    return [product_response(product) for product in product_service.list()]

@app.post("/api/v1/products", response_model=ProductResponse, status_code=202)
async def create_product(request: ProductCreateRequest) -> ProductResponse:
    product = product_service.create(request.topic, request.metadata, request.idempotency_key)
    return product_response(product)

@app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str) -> ProductResponse:
    try: return product_response(product_service.get(product_id))
    except KeyError as exc: raise HTTPException(status_code=404, detail="product not found") from exc

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
    try: product_service.get(product_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail="product not found") from exc
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
    products_list = product_service.list()
    jobs_list = job_service.list()
    return DashboardResponse(products=len(products_list), active_jobs=sum(j.status in {JobStatus.PENDING, JobStatus.RUNNING, JobStatus.RETRYING} for j in jobs_list), completed_products=sum(p.status == "completed" for p in products_list), revenue=None, sales=None, integrations=integration_service.status())
