"""FastAPI dependency-injection adapters."""

from typing import cast

from fastapi import Request

from coldchain.api.errors import ServiceUnavailableError
from coldchain.application.health import AiHealthService, ReadinessService
from coldchain.application.interfaces import TelemetryPublisher, WorkflowRepository
from coldchain.application.workflow import ApprovalService


def get_readiness_service(request: Request) -> ReadinessService:
    return cast(ReadinessService, request.app.state.readiness_service)


def get_ai_health_service(request: Request) -> AiHealthService:
    return cast(AiHealthService, request.app.state.ai_health_service)


def get_repository(request: Request) -> WorkflowRepository:
    repository = getattr(request.app.state, "workflow_repository", None)
    if repository is None:
        raise ServiceUnavailableError("workflow repository is unavailable")
    return cast(WorkflowRepository, repository)


def get_approval_service(request: Request) -> ApprovalService:
    service = getattr(request.app.state, "approval_service", None)
    if service is None:
        raise ServiceUnavailableError("approval service is unavailable")
    return cast(ApprovalService, service)


def get_telemetry_publisher(request: Request) -> TelemetryPublisher:
    publisher = getattr(request.app.state, "telemetry_publisher", None)
    if publisher is None:
        raise ServiceUnavailableError("telemetry publisher is unavailable")
    return cast(TelemetryPublisher, publisher)
