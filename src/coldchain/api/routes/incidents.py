"""Versioned governed-incident API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException

from coldchain.api.auth import local_identity
from coldchain.api.dependencies import (
    get_approval_service,
    get_repository,
    get_telemetry_publisher,
)
from coldchain.api.schemas import (
    CommandStatusView,
    DecisionRequest,
    DecisionResponse,
    IncidentView,
    TelemetryAccepted,
    TimelineEventView,
)
from coldchain.application.interfaces import Identity, TelemetryPublisher, WorkflowRepository
from coldchain.application.workflow import ApprovalService
from coldchain.contracts.models import TelemetryEvent
from coldchain.domain import ApprovalDecision

router = APIRouter()


@router.post(
    "/telemetry",
    response_model=TelemetryAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_telemetry(
    event: TelemetryEvent,
    publisher: Annotated[TelemetryPublisher, Depends(get_telemetry_publisher)],
) -> TelemetryAccepted:
    await publisher.publish(event)
    return TelemetryAccepted(event_id=event.event_id, status="ACCEPTED")


@router.get("/incidents", response_model=list[IncidentView])
async def list_incidents(
    repository: Annotated[WorkflowRepository, Depends(get_repository)],
) -> list[dict[str, object]]:
    return await repository.list_incidents()


@router.get("/incidents/{incident_id}", response_model=IncidentView)
async def get_incident(
    incident_id: UUID,
    repository: Annotated[WorkflowRepository, Depends(get_repository)],
) -> dict[str, object]:
    incident = await repository.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@router.get("/incidents/{incident_id}/timeline", response_model=list[TimelineEventView])
async def get_timeline(
    incident_id: UUID,
    repository: Annotated[WorkflowRepository, Depends(get_repository)],
) -> list[dict[str, object]]:
    if await repository.get_incident(incident_id) is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return await repository.timeline(incident_id)


async def _decide(
    incident_id: UUID,
    recommendation_id: UUID,
    body: DecisionRequest,
    request: Request,
    identity: Identity,
    service: ApprovalService,
    decision: ApprovalDecision,
) -> dict[str, object]:
    return await service.decide(
        incident_id,
        recommendation_id,
        identity,
        decision,
        body.rationale,
        body.idempotency_key,
        UUID(request.state.correlation_id),
    )


@router.post(
    "/incidents/{incident_id}/recommendations/{recommendation_id}/approve",
    response_model=DecisionResponse,
)
async def approve(
    incident_id: UUID,
    recommendation_id: UUID,
    body: DecisionRequest,
    request: Request,
    identity: Annotated[Identity, Depends(local_identity)],
    service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> dict[str, object]:
    return await _decide(
        incident_id,
        recommendation_id,
        body,
        request,
        identity,
        service,
        ApprovalDecision.APPROVED,
    )


@router.post(
    "/incidents/{incident_id}/recommendations/{recommendation_id}/reject",
    response_model=DecisionResponse,
)
async def reject(
    incident_id: UUID,
    recommendation_id: UUID,
    body: DecisionRequest,
    request: Request,
    identity: Annotated[Identity, Depends(local_identity)],
    service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> dict[str, object]:
    return await _decide(
        incident_id,
        recommendation_id,
        body,
        request,
        identity,
        service,
        ApprovalDecision.REJECTED,
    )


@router.get("/commands/{command_id}", response_model=CommandStatusView)
async def command_status(
    command_id: UUID,
    repository: Annotated[WorkflowRepository, Depends(get_repository)],
) -> dict[str, object]:
    command = await repository.command_status(command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="command not found")
    return command
