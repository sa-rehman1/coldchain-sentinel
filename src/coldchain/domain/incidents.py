"""Pure domain types for the governed incident workflow."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


class IncidentState(StrEnum):
    OPEN = "OPEN"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


_TRANSITIONS: dict[IncidentState, frozenset[IncidentState]] = {
    IncidentState.OPEN: frozenset({IncidentState.EVIDENCE_COLLECTED, IncidentState.FAILED}),
    IncidentState.EVIDENCE_COLLECTED: frozenset(
        {IncidentState.AWAITING_APPROVAL, IncidentState.FAILED}
    ),
    IncidentState.AWAITING_APPROVAL: frozenset(
        {IncidentState.APPROVED, IncidentState.REJECTED, IncidentState.FAILED}
    ),
    IncidentState.APPROVED: frozenset({IncidentState.EXECUTING, IncidentState.FAILED}),
    IncidentState.EXECUTING: frozenset({IncidentState.RESOLVED, IncidentState.FAILED}),
    IncidentState.REJECTED: frozenset(),
    IncidentState.RESOLVED: frozenset(),
    IncidentState.FAILED: frozenset(),
}


class InvalidStateTransition(ValueError):
    pass


def transition(current: IncidentState, target: IncidentState) -> IncidentState:
    if target not in _TRANSITIONS[current]:
        raise InvalidStateTransition(f"cannot transition incident from {current} to {target}")
    return target


@dataclass(frozen=True, slots=True)
class Incident:
    incident_id: UUID
    shipment_id: UUID
    state: IncidentState
    severity: str
    policy_version: str
    source_event_ids: tuple[UUID, ...]
    correlation_id: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.created_at)


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    evidence_id: UUID
    incident_id: UUID
    telemetry_event_ids: tuple[UUID, ...]
    policy_inputs: dict[str, Any]
    summary: str
    content_hash: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class Recommendation:
    recommendation_id: UUID
    incident_id: UUID
    evidence_ids: tuple[UUID, ...]
    action_type: str
    parameters: dict[str, str | int | float | bool]
    provider: str
    author_identity: str
    rationale: str
    expires_at: datetime
    non_authoritative: bool = True


@dataclass(frozen=True, slots=True)
class GovernanceEvaluation:
    evaluation_id: UUID
    incident_id: UUID
    recommendation_id: UUID
    decision: str
    policy_version: str
    reason_codes: tuple[str, ...]
    inputs: dict[str, Any]
    evaluated_at: datetime


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class Approval:
    approval_id: UUID
    incident_id: UUID
    recommendation_id: UUID
    actor_id: str
    actor_role: str
    decision: ApprovalDecision
    rationale: str
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class Command:
    command_id: UUID
    incident_id: UUID
    recommendation_id: UUID
    approval_id: UUID
    action_type: str
    parameters: dict[str, str | int | float | bool]
    idempotency_key: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ActionResult:
    result_id: UUID
    command_id: UUID
    status: str
    adapter: str
    detail: str
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class AuditEvent:
    audit_event_id: UUID
    incident_id: UUID
    event_type: str
    actor_id: str
    correlation_id: UUID
    causation_id: UUID | None
    component_version: str
    schema_version: str
    payload: dict[str, Any]
    occurred_at: datetime
    previous_event_hash: str | None
    event_hash: str
