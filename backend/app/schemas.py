from datetime import date, datetime
from typing import Any, Literal
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
    operating_profit: float | None = None
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
    operating_profit: float | None = None
    costs: dict[str, float] = Field(default_factory=dict)

class IntegrationStatus(BaseModel):
    name: str
    status: str
    message: str

class OpportunityCreateRequest(BaseModel):
    type: Literal["product", "service"]
    title: str = Field(min_length=3, max_length=240)
    description: str | None = None
    source: str | None = None
    source_url: str | None = None
    signals: dict[str, float] = Field(default_factory=dict)
    status: str = "discovered"
    idempotency_key: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)

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
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

class ServiceCreateRequest(BaseModel):
    opportunity_id: str | None = None
    title: str = Field(min_length=3, max_length=240)
    briefing: str | None = None
    status: str = "candidate"
    difficulty: float | None = Field(default=None, ge=0, le=100)
    estimated_hours: float | None = Field(default=None, ge=0)
    estimated_value: float = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

class ServiceResponse(BaseModel):
    id: str
    opportunity_id: str | None = None
    title: str
    briefing: str | None = None
    status: str
    difficulty: float | None = None
    estimated_hours: float | None = None
    estimated_value: float | None = None
    estimated_cost: float | None = None
    estimated_profit: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

class ControlResponse(BaseModel):
    kill_switch: bool
    paused_domains: list[str] = Field(default_factory=list)
    daily_ai_budget: float | None = None
    daily_ads_budget: float | None = None
    daily_total_budget: float | None = None
    human_approval_mode: str

class ControlUpdateRequest(BaseModel):
    kill_switch: bool | None = None
    paused_domains: list[str] | None = None
    daily_ai_budget: float | None = Field(default=None, ge=0)
    daily_ads_budget: float | None = Field(default=None, ge=0)
    daily_total_budget: float | None = Field(default=None, ge=0)
    human_approval_mode: str | None = None

class EventCreateRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    provider: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)

class EventResponse(BaseModel):
    id: str
    event_type: str
    provider: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
