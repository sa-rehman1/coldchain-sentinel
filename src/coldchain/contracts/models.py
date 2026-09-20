"""Pydantic contracts serialized as versioned JSON messages."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
        use_enum_values=True,
    )


class EventMetadata(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: UUID
    correlation_id: UUID
    occurred_at: datetime
    producer: str = Field(min_length=1, max_length=100)

    @field_validator("occurred_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        return _aware_utc(value)


class TelemetryEvent(EventMetadata):
    shipment_id: UUID
    vehicle_id: str = Field(min_length=1, max_length=100)
    sensor_id: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    temperature_celsius: float = Field(ge=-100, le=100)
    cargo_type: str = Field(min_length=1, max_length=100)
    reading_sequence: int = Field(ge=0)


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RESOLVED = "RESOLVED"


class Incident(EventMetadata):
    incident_id: UUID
    shipment_id: UUID
    incident_type: str = Field(min_length=1, max_length=100)
    status: IncidentStatus
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    detection_rule: str = Field(min_length=1, max_length=200)
    source_event_ids: tuple[UUID, ...] = Field(min_length=1)


class EvidenceType(StrEnum):
    TELEMETRY = "TELEMETRY"
    WEATHER = "WEATHER"
    POLICY = "POLICY"
    OPERATIONAL = "OPERATIONAL"


class EvidenceItem(EventMetadata):
    evidence_id: UUID
    incident_id: UUID
    evidence_type: EvidenceType
    source: str = Field(min_length=1, max_length=200)
    source_version: str = Field(min_length=1, max_length=100)
    observed_at: datetime
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    summary: str = Field(min_length=1, max_length=2000)

    _validate_observed_at = field_validator("observed_at")(_aware_utc)


class RecommendedAction(ContractModel):
    action_type: str = Field(min_length=1, max_length=100)
    parameters: dict[str, str | int | float | bool]


class Recommendation(EventMetadata):
    recommendation_id: UUID
    incident_id: UUID
    evidence_references: tuple[UUID, ...] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    uncertainty: str = Field(min_length=1, max_length=2000)
    policy_version: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=100)
    recommendation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime
    recommended_action: RecommendedAction
    authorization_statement: Literal["THIS_RECOMMENDATION_IS_NOT_AUTHORIZATION"]

    _validate_expires_at = field_validator("expires_at")(_aware_utc)


class ApprovalValue(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalDecision(EventMetadata):
    approval_id: UUID
    recommendation_id: UUID
    incident_id: UUID
    reviewer_identity: str = Field(min_length=1, max_length=200)
    decision: ApprovalValue
    decided_at: datetime
    rationale: str = Field(min_length=1, max_length=2000)
    recommendation_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_version: str = Field(min_length=1, max_length=100)

    _validate_decided_at = field_validator("decided_at")(_aware_utc)


class ActionCommand(EventMetadata):
    command_id: UUID
    incident_id: UUID
    approval_id: UUID
    recommendation_id: UUID
    action_type: str = Field(min_length=1, max_length=100)
    parameters: dict[str, str | int | float | bool]
    idempotency_key: str = Field(min_length=16, max_length=200)
    policy_version: str = Field(min_length=1, max_length=100)


class AuditEvent(EventMetadata):
    audit_event_id: UUID
    actor_type: Literal["USER", "SERVICE", "SYSTEM"]
    actor_id: str = Field(min_length=1, max_length=200)
    event_type: str = Field(min_length=1, max_length=200)
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any]
    previous_event_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    event_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class FailureEnvelope(EventMetadata):
    failed_topic: str = Field(min_length=1, max_length=200)
    failed_partition: int = Field(ge=0)
    failed_offset: int = Field(ge=0)
    failure_type: Literal["INVALID_MESSAGE"]
    reason_code: str = Field(min_length=1, max_length=100)
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    encoded_payload_base64: str = Field(min_length=1, max_length=1_500_000)
