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


class TelemetryReadingView(ApiModel):
    event_id: UUID
    occurred_at: str
    reading_sequence: int
    temperature_celsius: float
    cargo_type: str
    disposition: str
    policy_inputs: dict[str, Any]
    reason_codes: list[str]


class EvidenceSnapshotView(ApiModel):
    evidence_id: UUID
    telemetry_event_ids: list[UUID]
    policy_inputs: dict[str, Any]
    summary: str
    content_hash: str
    captured_at: str


class RecommendationDetailView(ApiModel):
    recommendation_id: UUID
    evidence_ids: list[UUID]
    action_type: str
    parameters: dict[str, Any]
    provider: str
    author_identity: str
    rationale: str
    expires_at: str
    non_authoritative: bool
    provenance: dict[str, Any]


class GovernanceEvaluationView(ApiModel):
    evaluation_id: UUID
    recommendation_id: UUID
    decision: str
    policy_version: str
    reason_codes: list[str]
    inputs: dict[str, Any]
    evaluated_at: str


class ApprovalView(ApiModel):
    approval_id: UUID
    recommendation_id: UUID
    actor_id: str
    actor_role: str
    decision: str
    rationale: str
    decided_at: str


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
    recommendation_provenance: dict[str, Any] | None = None
    telemetry: list[TelemetryReadingView] = Field(default_factory=list)
    evidence: EvidenceSnapshotView | None = None
    recommendation: RecommendationDetailView | None = None
    governance: GovernanceEvaluationView | None = None
    approval: ApprovalView | None = None
    command: "CommandStatusView | None" = None


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
    action_result: ActionResultView | None = None


class DemoScenarioView(ApiModel):
    scenario_id: str
    title: str
    description: str
    expected_outcome: str
    human_action: str


class DemoRunStarted(ApiModel):
    run_id: UUID
    scenario_id: str
    correlation_id: UUID
    shipment_id: UUID
    event_ids: list[UUID]
    publish_count: int
    status: str


class DemoRunSteps(ApiModel):
    telemetry_submitted: bool
    event_accepted: bool
    policy_evaluated: bool
    evidence_collected: bool
    recommendation_created: bool
    governance_completed: bool
    incident_ready: bool


class DemoRunStatus(ApiModel):
    run_id: UUID
    scenario_id: str
    correlation_id: UUID
    shipment_id: UUID
    event_ids: list[UUID]
    publish_count: int
    started_at: str
    status: str
    processed_event_count: int
    dispositions: list[str]
    incident: IncidentView | None
    steps: DemoRunSteps


IncidentView.model_rebuild()
