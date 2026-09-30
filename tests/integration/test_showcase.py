import os
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy import func, select

from coldchain.application.showcase import SHOWCASE_SHIPMENTS
from coldchain.infrastructure.database import Database
from coldchain.infrastructure.models import (
    ApprovalRecord,
    AuditEventRecord,
    CommandRecord,
    IncidentRecord,
)
from coldchain.infrastructure.repositories import SqlWorkflowRepository
from coldchain.infrastructure.showcase import prepare_showcase


def _url() -> str:
    value = os.getenv("COLDCHAIN_TEST_DATABASE_URL")
    if not value:
        pytest.skip("COLDCHAIN_TEST_DATABASE_URL is not configured")
    return value


@pytest.mark.integration
async def test_showcase_seed_is_idempotent_and_dashboard_is_reconciled() -> None:
    database = Database(_url())
    stable_ids = tuple(shipment.shipment_id for shipment in SHOWCASE_SHIPMENTS)
    fixed_now = datetime.now(UTC)
    try:
        async with database.transaction() as session:
            approvals_before = await session.scalar(
                select(func.count())
                .select_from(ApprovalRecord)
                .join(IncidentRecord, ApprovalRecord.incident_id == IncidentRecord.incident_id)
                .where(IncidentRecord.shipment_id.in_(stable_ids))
            )
            commands_before = await session.scalar(
                select(func.count())
                .select_from(CommandRecord)
                .join(IncidentRecord, CommandRecord.incident_id == IncidentRecord.incident_id)
                .where(IncidentRecord.shipment_id.in_(stable_ids))
            )
        first = await prepare_showcase(database, now=fixed_now)
        async with database.transaction() as session:
            audit_count_after_first = await session.scalar(
                select(func.count())
                .select_from(AuditEventRecord)
                .join(IncidentRecord, AuditEventRecord.incident_id == IncidentRecord.incident_id)
                .where(IncidentRecord.shipment_id.in_(stable_ids))
            )
        second = await prepare_showcase(database, now=fixed_now)
        repository = SqlWorkflowRepository(database)
        dashboard = await repository.dashboard()
        incidents = await repository.list_showcase_incidents()
        async with database.transaction() as session:
            approvals_after = await session.scalar(
                select(func.count())
                .select_from(ApprovalRecord)
                .join(IncidentRecord, ApprovalRecord.incident_id == IncidentRecord.incident_id)
                .where(IncidentRecord.shipment_id.in_(stable_ids))
            )
            commands_after = await session.scalar(
                select(func.count())
                .select_from(CommandRecord)
                .join(IncidentRecord, CommandRecord.incident_id == IncidentRecord.incident_id)
                .where(IncidentRecord.shipment_id.in_(stable_ids))
            )
            audit_count_after_second = await session.scalar(
                select(func.count())
                .select_from(AuditEventRecord)
                .join(IncidentRecord, AuditEventRecord.incident_id == IncidentRecord.incident_id)
                .where(IncidentRecord.shipment_id.in_(stable_ids))
            )

        assert first == second
        assert approvals_after == approvals_before
        assert commands_after == commands_before
        assert audit_count_after_first == audit_count_after_second == 20
        assert dashboard["metrics"] == {
            "affectedShipments": 4,
            "openIncidents": 3,
            "awaitingHumanReview": 2,
        }
        assert dashboard["severityDistribution"] == {
            "critical": 2,
            "warning": 2,
            "normal": 0,
        }
        human_decisions = dashboard["humanDecisions"]
        assert isinstance(human_decisions, list)
        assert all(item["incidentReference"].startswith("INC-") for item in human_decisions)
        assert all(
            item["reviewerRole"] in {"Dispatcher", "Administrator"} for item in human_decisions
        )
        assert all("actor" not in key.lower() for item in human_decisions for key in item)
        latest = dashboard["latestShipments"]
        assert isinstance(latest, list)
        assert len(latest) == len({item["shipmentReference"] for item in latest}) <= 5
        assert all(item["shipmentReference"].startswith("CCS-") for item in latest)
        assert all("-" not in item["shipmentReference"][4:] for item in latest)
        assert [item["incidentReference"] for item in incidents] == [
            "INC-1001",
            "INC-1002",
            "INC-1003",
            "INC-1004",
        ]
        assert [item["shipmentReference"] for item in incidents] == [
            "CCS-1001",
            "CCS-1002",
            "CCS-1003",
            "CCS-1004",
        ]
        assert [item["sensorLabel"] for item in incidents] == [
            "Probe 01",
            "Probe 02",
            "Probe 03",
            "Probe 04",
        ]
        assert all(item["reviewerLabel"] in {"Unassigned", "Dispatcher"} for item in incidents)
        assert all(item["productLabel"] for item in incidents)
        assert all(item["telemetry"] for item in incidents)
        assert all(
            item["evidenceProfile"]
            == {
                "sensorHealth": "Healthy",
                "calibration": "Verified",
                "sampleIntervalMinutes": 10,
                "readingQuality": "No quality flags",
                "productSensitivity": "High",
                "custodyVerification": "Complete",
                "complete": True,
            }
            for item in incidents
        )
        first_incident = cast(dict[str, Any], incidents[0])
        sop_evidence = cast(list[dict[str, Any]], first_incident["sopEvidence"])
        assert [item["documentId"] for item in sop_evidence] == [
            "CCS-SOP-TEMP-001",
            "CCS-SOP-HOLD-001",
        ]
        assert all(item["chunkId"].startswith("sopch_") for item in sop_evidence)
        assert all(item["validationStatus"] == "trusted" for item in sop_evidence)
        assert all(item["effectiveDate"] <= fixed_now.date().isoformat() for item in sop_evidence)
        recommendation = cast(dict[str, Any], first_incident["recommendation"])
        provenance = cast(dict[str, Any], recommendation["provenance"])
        assert provenance["citedChunkIds"] == [item["chunkId"] for item in sop_evidence]
        assert provenance["evidenceSufficient"] is True
        assert provenance["missingInformation"] == []
        assert provenance["contraindications"] == []
        assert provenance["uncertaintyLevel"] == "low"
        assert provenance["fallbackUsed"] is False
        governance = cast(dict[str, Any], first_incident["governance"])
        checks = cast(list[dict[str, Any]], governance["checks"])
        assert governance["decision"] == "APPROVAL_REQUIRED"
        assert [item["name"] for item in checks] == [
            "Schema check",
            "Evidence check",
            "Citation check",
            "Policy check",
            "Expiry check",
            "Kill-switch state",
            "Human approval",
        ]
        assert all(item["state"] in {"pass", "warning"} for item in checks)
        timeline = await repository.timeline(UUID(str(first_incident["incidentId"])))
        assert [item["eventType"] for item in timeline] == [
            "TELEMETRY_RECEIVED",
            "BREACH_POLICY_EVALUATED",
            "EVIDENCE_SNAPSHOT_CREATED",
            "RECOMMENDATION_CREATED",
            "GOVERNANCE_EVALUATED",
        ]
        assert not {
            "HUMAN_DECISION_RECORDED",
            "COMMAND_CREATED",
            "SIMULATED_ACTION_COMPLETED",
        } & {item["eventType"] for item in timeline}
        assert all(item["hashChainVerified"] is True for item in timeline)
    finally:
        await database.dispose()
