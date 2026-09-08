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
