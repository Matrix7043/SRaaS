from typing import Any, Optional
from pydantic import BaseModel, Field


class DeployResponse(BaseModel):
    deployment_id: str
    container_name: str
    invocation_url: str


class InvokeRequest(BaseModel):
    version: str = "v1"
    event: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class InvokeResponse(BaseModel):
    result: Optional[Any] = None
    logs: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0


class DeleteResponse(BaseModel):
    deployment_id: str
    message: str


class HealthResponse(BaseModel):
    status: str
    docker_available: bool
