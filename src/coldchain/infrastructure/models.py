"""SQLAlchemy persistence models for the governed vertical slice."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    pass


class PlatformMetadata(Base):
    __tablename__ = "platform_metadata"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    shipment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    correlation_id: Mapped[UUID] = mapped_column(Uuid)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reading_sequence: Mapped[int]
    temperature_celsius: Mapped[float]
    cargo_type: Mapped[str] = mapped_column(String(100))
    disposition: Mapped[str] = mapped_column(String(40))
    policy_version: Mapped[str] = mapped_column(String(100))
    policy_inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IncidentRecord(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    shipment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    state: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    policy_version: Mapped[str] = mapped_column(String(100))
    source_event_ids: Mapped[list[str]] = mapped_column(JSONB)
    correlation_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvidenceRecord(Base):
    __tablename__ = "evidence_snapshots"

    evidence_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    telemetry_event_ids: Mapped[list[str]] = mapped_column(JSONB)
    policy_inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    summary: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecommendationRecord(Base):
    __tablename__ = "recommendations"

    recommendation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    action_type: Mapped[str] = mapped_column(String(100))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provider: Mapped[str] = mapped_column(String(100))
    author_identity: Mapped[str] = mapped_column(String(200))
    rationale: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    non_authoritative: Mapped[bool]
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class GovernanceRecord(Base):
    __tablename__ = "governance_evaluations"

    evaluation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    recommendation_id: Mapped[UUID] = mapped_column(ForeignKey("recommendations.recommendation_id"))
    decision: Mapped[str] = mapped_column(String(40))
    policy_version: Mapped[str] = mapped_column(String(100))
    reason_codes: Mapped[list[str]] = mapped_column(JSONB)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    approval_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendations.recommendation_id"), unique=True
    )
    actor_id: Mapped[str] = mapped_column(String(200))
    actor_role: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommandRecord(Base):
    __tablename__ = "commands"

    command_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    recommendation_id: Mapped[UUID] = mapped_column(ForeignKey("recommendations.recommendation_id"))
    approval_id: Mapped[UUID] = mapped_column(ForeignKey("approvals.approval_id"))
    action_type: Mapped[str] = mapped_column(String(100))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ActionResultRecord(Base):
    __tablename__ = "action_results"

    result_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    command_id: Mapped[UUID] = mapped_column(ForeignKey("commands.command_id"), unique=True)
    status: Mapped[str] = mapped_column(String(40))
    adapter: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    sequence: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    audit_event_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.incident_id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    actor_id: Mapped[str] = mapped_column(String(200))
    correlation_id: Mapped[UUID] = mapped_column(Uuid)
    causation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    component_version: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)
