"""Typed HTTP request and response models for Milestone 1A."""

from typing import Any, Literal
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
    evidence_reference: str | None = None
    telemetry_event_ids: list[UUID]
    policy_inputs: dict[str, Any]
    summary: str
    content_hash: str
    captured_at: str


class RecommendationActionabilityView(ApiModel):
    state: Literal["AWAITING_HUMAN_REVIEW", "EXPIRED", "DECIDED"]
    approval_allowed: bool
    rejection_allowed: bool
    status: str
    explanation: str
    expires_in_minutes: int | None


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
    actionability: RecommendationActionabilityView


class SopEvidenceView(ApiModel):
    chunk_id: str
    document_id: str
    document_title: str
    document_version: str
    section_id: str
    section_title: str
    effective_date: str
    excerpt: str
    why_applicable: str
    validation_status: str


class GovernanceCheckView(ApiModel):
    name: str
    state: str
    detail: str


class GovernanceEvaluationView(ApiModel):
    evaluation_id: UUID
    recommendation_id: UUID
    decision: str
    policy_version: str
    reason_codes: list[str]
    inputs: dict[str, Any]
    evaluated_at: str
    authority: str | None = None
    checks: list[GovernanceCheckView] = Field(default_factory=list)


class ApprovalView(ApiModel):
    approval_id: UUID
    recommendation_id: UUID
    actor_id: str
    actor_role: str
    decision: str
    rationale: str
    decided_at: str


class IncidentEvidenceProfileView(ApiModel):
    sensor_health: str
    calibration: str
    sample_interval_minutes: int
    reading_quality: str
    product_sensitivity: str
    custody_verification: str
    complete: bool


class IncidentView(ApiModel):
    incident_id: UUID
    shipment_id: UUID
    incident_reference: str | None = None
    shipment_reference: str | None = None
    route: dict[str, object] | None = None
    product_label: str | None = None
    sensor_label: str | None = None
    reviewer_label: str | None = None
    evidence_profile: IncidentEvidenceProfileView | None = None
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
    sop_evidence: list[SopEvidenceView] = Field(default_factory=list)
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
    hash_chain_verified: bool


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


class DashboardMetricsView(ApiModel):
    affected_shipments: int = Field(ge=0)
    open_incidents: int = Field(ge=0)
    awaiting_human_review: int = Field(ge=0)


class SeverityDistributionView(ApiModel):
    critical: int = Field(ge=0)
    warning: int = Field(ge=0)
    normal: int = Field(ge=0)


class DashboardRouteView(ApiModel):
    origin: str
    via: str
    destination: str
    progress: int = Field(ge=0, le=100)


class DashboardShipmentView(ApiModel):
    incident_id: UUID
    incident_reference: str
    shipment_id: UUID
    shipment_reference: str
    route: DashboardRouteView
    product: str
    current_temperature_celsius: float
    permitted_min_celsius: float
    permitted_max_celsius: float
    state: str
    severity: str
    created_at: str
    updated_at: str
    last_reading_at: str
    age_minutes: int = Field(ge=0)
    trend_celsius: list[float]
    reason_codes: list[str]
    recommended_action: str | None = None
    governance_decision: str | None = None
    recommendation_expires_at: str | None = None


class ApprovalQueueSummaryView(ApiModel):
    pending: int = Field(ge=0)
    oldest_waiting_minutes: int = Field(ge=0)
    expiring_within_15_minutes: int = Field(ge=0)


class DashboardHumanDecisionView(ApiModel):
    incident_id: UUID
    incident_reference: str
    decision: str
    reviewer_role: str
    decided_at: str


class IncidentActivityBucketView(ApiModel):
    label: str
    starts_at: str
    critical: int = Field(ge=0)
    warning: int = Field(ge=0)
    resolved: int = Field(ge=0)


class DashboardView(ApiModel):
    generated_at: str
    scope: str
    metrics: DashboardMetricsView
    severity_distribution: SeverityDistributionView
    latest_shipments: list[DashboardShipmentView] = Field(max_length=5)
    approval_queue: ApprovalQueueSummaryView
    human_decisions: list[DashboardHumanDecisionView]
    activity: list[IncidentActivityBucketView]


class ObservabilityServiceView(ApiModel):
    name: str
    status: Literal["HEALTHY", "DEGRADED", "UNAVAILABLE", "OPTIONAL_NOT_STARTED"]
    signal: str
    measurement: float | None = None
    measurement_unit: str | None = None
    checked_at: str
    inspection_url: str | None = None


class ObservabilityMetricView(ApiModel):
    key: str
    label: str
    value: float | None = None
    unit: str
    state: Literal["AVAILABLE", "NO_SAMPLES", "UNAVAILABLE"]
    source: str


class ObservabilityPointView(ApiModel):
    timestamp: str
    value: float


class ObservabilitySeriesView(ApiModel):
    api_request_rate: list[ObservabilityPointView]
    api_p95_latency: list[ObservabilityPointView]
    worker_throughput: list[ObservabilityPointView]
    dlq_activity: list[ObservabilityPointView]


class ObservabilityAlertRuleView(ApiModel):
    name: str
    state: str
    severity: str
    summary: str


class ObservabilityAlertsView(ApiModel):
    state: Literal["AVAILABLE", "UNAVAILABLE"]
    rules: list[ObservabilityAlertRuleView] = Field(max_length=20)


class ObservabilityTraceView(ApiModel):
    trace_id: str
    operation: str
    duration_ms: float = Field(ge=0)
    span_count: int = Field(ge=0)
    started_at: str


class ObservabilityTracesView(ApiModel):
    state: Literal["AVAILABLE", "NO_SAMPLES", "UNAVAILABLE"]
    items: list[ObservabilityTraceView] = Field(max_length=5)


class ObservabilitySummaryView(ApiModel):
    generated_at: str
    overall_status: Literal["HEALTHY", "DEGRADED"]
    healthy_services: int = Field(ge=0)
    total_services: int = Field(ge=0)
    active_alerts: int = Field(ge=0)
    auto_refresh_seconds: int = Field(ge=10, le=15)
    services: list[ObservabilityServiceView]
    metrics: list[ObservabilityMetricView]
    series: ObservabilitySeriesView
    alerts: ObservabilityAlertsView
    traces: ObservabilityTracesView
    privacy_notice: str


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


DemoStageState = Literal["PENDING", "COMPLETED", "NOT_REQUIRED", "BLOCKED", "FAILED"]


class DemoRunSteps(ApiModel):
    sensor_reading: DemoStageState
    policy_check: DemoStageState
    incident_created: DemoStageState
    evidence_collected: DemoStageState
    ai_advisory: DemoStageState
    governance: DemoStageState
    human_review: DemoStageState


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
    incident_id: UUID | None
    incident_reference: str | None
    shipment_reference: str | None
    incident_severity: str | None
    governance_decision: str | None
    human_decision_recorded: bool
    result_state: Literal["PROCESSING", "COMPLETE", "AWAITING_HUMAN_REVIEW", "BLOCKED", "FAILED"]
    steps: DemoRunSteps


IncidentView.model_rebuild()
