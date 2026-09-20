"""Kubernetes- and Compose-compatible health endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from coldchain.api.dependencies import get_ai_health_service, get_readiness_service
from coldchain.api.errors import ServiceUnavailableError
from coldchain.application.health import AiHealthService, ReadinessService

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["alive"] = "alive"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"] = "ready"
    checks: dict[str, str]


class AiHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_provider: str
    provider_configured: bool
    live_calls_enabled: bool
    qdrant_readiness: str
    embedding_provider_readiness: str
    fallback_available: bool


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> ReadinessResponse:
    result = await service.check()
    if not result.ready:
        raise ServiceUnavailableError("one or more required dependencies are unavailable")
    return ReadinessResponse(checks=result.checks)


@router.get("/ai", response_model=AiHealthResponse)
async def ai_health(
    service: Annotated[AiHealthService, Depends(get_ai_health_service)],
) -> AiHealthResponse:
    return AiHealthResponse.model_validate(service.check(), from_attributes=True)
