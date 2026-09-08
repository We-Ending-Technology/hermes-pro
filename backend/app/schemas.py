from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str

class AgentRunRequest(BaseModel):
    agent: str = Field(min_length=1, max_length=100)
    input: dict = Field(default_factory=dict)

class AgentRunResponse(BaseModel):
    run_id: str
    agent: str
    status: str
    output: dict

class ProductionRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)

class ProductionResponse(BaseModel):
    job_id: str
    status: str

class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    attempts: int
    error_message: str | None = None

class DashboardResponse(BaseModel):
    jobs: int
    products: int
    running: int
    failures: int
    worker: str
