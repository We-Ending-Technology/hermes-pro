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

class OpportunityCreateRequest(BaseModel):
    type: str = Field(default="product", pattern="^(product|service)$")
    title: str = Field(min_length=3, max_length=240)
    description: str | None = None
    source: str | None = None
    source_url: str | None = None
    signals: dict[str, Any] = Field(default_factory=dict)
    score: float | None = Field(default=None, ge=0, le=100)
    confidence: float | None = Field(default=None, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)

class OpportunityResponse(BaseModel):
    id: str
    type: str
    title: str
    description: str | None = None
    source: str | None = None
    source_url: str | None = None
    signals: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None
    confidence: float | None = None
    status: str
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

class ControlRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool

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
