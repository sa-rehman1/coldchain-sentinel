"""Typed HTTP request and response models for Milestone 1A."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)


class TelemetryAccepted(ApiModel):
    event_id: UUID
    status: str


class IncidentView(ApiModel):
    incident_id: UUID
    shipment_id: UUID
    state: str
    severity: str
    policy_version: str
    source_event_ids: list[UUID]
    correlation_id: UUID
    created_at: str
    updated_at: str
    recommendation_id: UUID | None = None
    recommended_action: str | None = None
    recommendation_expires_at: str | None = None


class TimelineEventView(ApiModel):
    sequence: int
    audit_event_id: UUID
    event_type: str
    actor_id: str
    correlation_id: UUID
    causation_id: UUID | None
    component_version: str
    schema_version: str
    payload: dict[str, Any]
    occurred_at: str
    previous_event_hash: str | None
    event_hash: str


class DecisionRequest(ApiModel):
    rationale: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=16, max_length=200)


class ActionResultView(ApiModel):
    result_id: UUID
    status: str
    adapter: str
    detail: str
    completed_at: str


class DecisionResponse(ApiModel):
    approval_id: UUID
    decision: str
    idempotent_replay: bool
    command_id: UUID | None = None
    status: str | None = None
    action_result: ActionResultView | None = None


class CommandStatusView(ApiModel):
    command_id: UUID
    incident_id: UUID
    action_type: str
    status: str
    adapter: str | None
    detail: str | None
