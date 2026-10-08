from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str

class AgentRunRequest(BaseModel):
    agent: str = Field(min_length=1, max_length=100)
    input: dict[str, Any] = Field(default_factory=dict)

class AgentRunResponse(BaseModel):
    run_id: str
    agent: str
    status: str
    output: dict[str, Any]

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

class ChatResponse(BaseModel):
    response: str
    provider: str
    model: str

class ProductCreateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=240)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)

class ProductResponse(BaseModel):
    id: str
    topic: str
    title: str | None = None
    status: str
    current_stage: str
    stages: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    attempts: int
    max_attempts: int
    error_message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

class RadarRequest(BaseModel):
    demand: float = Field(default=50, ge=0, le=100)
    competition: float = Field(default=50, ge=0, le=100)
    differentiation: float = Field(default=50, ge=0, le=100)
    production_difficulty: float = Field(default=50, ge=0, le=100)
    pricing_potential: float = Field(default=50, ge=0, le=100)
    audience_clarity: float = Field(default=50, ge=0, le=100)

class RadarResponse(BaseModel):
    score: int
    confidence: int
    dimensions: dict[str, int]
    findings: list[str]

class OpportunityResponse(BaseModel):
    id: str | None = None
    source: str
    title: str
    url: str
    summary: str = ""
    score: int
    difficulty: str
    suggested_price: float | None = None
    currency: str = "BRL"
    proposal: str = ""
    status: str = "approved"
    application_status: str = "not_attempted"
    created_at: datetime | None = None

class RadarRunResponse(BaseModel):
    collected: int
    approved: int
    top: list[dict[str, Any]]
    ran_at: str
    new: int = 0
    duplicates_skipped: int = 0
    persisted: int = 0
    channels: dict[str, int] = Field(default_factory=dict)
    hunter: dict[str, Any] = Field(default_factory=dict)

class QualityResponse(BaseModel):
    score: int
    decision: str
    dimensions: dict[str, int]
    findings: list[str]
    safe_fixes: list[str]

class DashboardResponse(BaseModel):
    products: int
    active_jobs: int
    completed_products: int
    revenue: float | None = None
    sales: int | None = None
    integrations: list[dict[str, str]]

class SalesSummary(BaseModel):
    range_start: date | None = None
    range_end: date | None = None
    revenue: float | None = None
    orders: int | None = None
    ticket: float | None = None
    status: str
    message: str

class AnalyticsResponse(BaseModel):
    status: str
    insights: list[str]
    experiments: list[str]

class IntegrationStatus(BaseModel):
    name: str
    status: str
    message: str
