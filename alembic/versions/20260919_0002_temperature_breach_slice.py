"""Create governed temperature-breach workflow tables.

Revision ID: 20260919_0002
Revises: 20260919_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0002"
down_revision: str | None = "20260919_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid = postgresql.UUID(as_uuid=True)
json_value = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "telemetry_records",
        sa.Column("event_id", uuid, primary_key=True),
        sa.Column("shipment_id", uuid, nullable=False),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reading_sequence", sa.Integer(), nullable=False),
        sa.Column("temperature_celsius", sa.Float(), nullable=False),
        sa.Column("cargo_type", sa.String(100), nullable=False),
        sa.Column("disposition", sa.String(40), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("policy_inputs", json_value, nullable=False),
        sa.Column("reason_codes", json_value, nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_telemetry_records_shipment_id", "telemetry_records", ["shipment_id"])
    op.create_index("ix_telemetry_records_occurred_at", "telemetry_records", ["occurred_at"])
    op.create_table(
        "incidents",
        sa.Column("incident_id", uuid, primary_key=True),
        sa.Column("shipment_id", uuid, nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("source_event_ids", json_value, nullable=False),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_shipment_id", "incidents", ["shipment_id"])
    op.create_index("ix_incidents_state", "incidents", ["state"])
    op.create_table(
        "evidence_snapshots",
        sa.Column("evidence_id", uuid, primary_key=True),
        sa.Column("incident_id", uuid, sa.ForeignKey("incidents.incident_id"), nullable=False),
        sa.Column("telemetry_event_ids", json_value, nullable=False),
        sa.Column("policy_inputs", json_value, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_snapshots_incident_id", "evidence_snapshots", ["incident_id"])
    op.create_table(
        "recommendations",
        sa.Column("recommendation_id", uuid, primary_key=True),
        sa.Column("incident_id", uuid, sa.ForeignKey("incidents.incident_id"), nullable=False),
        sa.Column("evidence_ids", json_value, nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("parameters", json_value, nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("author_identity", sa.String(200), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("non_authoritative", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_recommendations_incident_id", "recommendations", ["incident_id"])
    op.create_table(
        "governance_evaluations",
        sa.Column("evaluation_id", uuid, primary_key=True),
        sa.Column("incident_id", uuid, sa.ForeignKey("incidents.incident_id"), nullable=False),
        sa.Column(
            "recommendation_id",
            uuid,
            sa.ForeignKey("recommendations.recommendation_id"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("reason_codes", json_value, nullable=False),
        sa.Column("inputs", json_value, nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_governance_evaluations_incident_id", "governance_evaluations", ["incident_id"]
    )
    op.create_table(
        "approvals",
        sa.Column("approval_id", uuid, primary_key=True),
        sa.Column("incident_id", uuid, sa.ForeignKey("incidents.incident_id"), nullable=False),
        sa.Column(
            "recommendation_id",
            uuid,
            sa.ForeignKey("recommendations.recommendation_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("actor_role", sa.String(100), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_approvals_incident_id", "approvals", ["incident_id"])
    op.create_table(
        "commands",
        sa.Column("command_id", uuid, primary_key=True),
        sa.Column("incident_id", uuid, sa.ForeignKey("incidents.incident_id"), nullable=False),
        sa.Column(
            "recommendation_id",
            uuid,
            sa.ForeignKey("recommendations.recommendation_id"),
            nullable=False,
        ),
        sa.Column("approval_id", uuid, sa.ForeignKey("approvals.approval_id"), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("parameters", json_value, nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_commands_incident_id", "commands", ["incident_id"])
    op.create_table(
        "action_results",
        sa.Column("result_id", uuid, primary_key=True),
        sa.Column(
            "command_id", uuid, sa.ForeignKey("commands.command_id"), nullable=False, unique=True
        ),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("adapter", sa.String(100), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("sequence", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("audit_event_id", uuid, nullable=False, unique=True),
        sa.Column("incident_id", uuid, sa.ForeignKey("incidents.incident_id"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("correlation_id", uuid, nullable=False),
        sa.Column("causation_id", uuid, nullable=True),
        sa.Column("component_version", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("payload", json_value, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_event_hash", sa.String(64), nullable=True),
        sa.Column("event_hash", sa.String(64), nullable=False, unique=True),
    )
    op.create_index("ix_audit_events_incident_id", "audit_events", ["incident_id"])
    op.execute(
        """
        CREATE FUNCTION reject_audit_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_event_mutation")
    for table in (
        "audit_events",
        "action_results",
        "commands",
        "approvals",
        "governance_evaluations",
        "recommendations",
        "evidence_snapshots",
        "incidents",
        "telemetry_records",
    ):
        op.drop_table(table)
