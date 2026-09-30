import asyncio
import os
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from coldchain.application.actions import SimulatedColdChainActionAdapter
from coldchain.application.demo import DemoScenarioService
from coldchain.application.interfaces import Identity
from coldchain.application.recommendations import DeterministicLocalRecommendationProvider
from coldchain.application.workflow import (
    ApprovalService,
    AuthorizationError,
    TemperatureBreachWorkflow,
    WorkflowConflictError,
)
from coldchain.contracts.models import TelemetryEvent
from coldchain.domain import ApprovalDecision
from coldchain.infrastructure.database import Database
from coldchain.infrastructure.models import (
    ActionResultRecord,
    ApprovalRecord,
    AuditEventRecord,
    CommandRecord,
    IncidentRecord,
    RecommendationRecord,
)
from coldchain.infrastructure.repositories import SqlWorkflowRepository


def _url() -> str:
    value = os.getenv("COLDCHAIN_TEST_DATABASE_URL")
    if not value:
        pytest.skip("COLDCHAIN_TEST_DATABASE_URL is not configured")
    return value


def _event() -> TelemetryEvent:
    return TelemetryEvent(
        event_id=uuid4(),
        correlation_id=uuid4(),
        occurred_at=datetime.now(UTC),
        producer="repository-integration-test",
        shipment_id=uuid4(),
        vehicle_id="vehicle-integration",
        sensor_id="sensor-integration",
        latitude=33.77,
        longitude=-118.19,
        temperature_celsius=10.5,
        cargo_type="FRESH_PERISHABLES",
        reading_sequence=1,
    )


@pytest.mark.integration
async def test_repository_duplicate_audit_approval_and_command_idempotency() -> None:
    database = Database(_url())
    repository = SqlWorkflowRepository(database)
    workflow = TemperatureBreachWorkflow(repository, DeterministicLocalRecommendationProvider())
    event = _event()
    try:
        before = len(await repository.list_incidents())
        first = await workflow.process(event)
        duplicate = await workflow.process(event)
        after = len(await repository.list_incidents())
        assert first.incident_id is not None
        assert duplicate.duplicate is True
        assert after == before + 1

        incident = await repository.get_incident(first.incident_id)
        assert incident is not None
        recommendation_id = incident["recommendationId"]
        assert isinstance(recommendation_id, str)
        assert incident["telemetry"]
        assert incident["evidence"]
        assert incident["recommendation"]
        assert incident["recommendation"]["actionability"]["state"] == ("AWAITING_HUMAN_REVIEW")
        assert incident["recommendation"]["actionability"]["approvalAllowed"] is True
        assert incident["recommendation"]["actionability"]["rejectionAllowed"] is True
        assert incident["governance"]
        timeline = await repository.timeline(first.incident_id)
        sequences = [int(str(item["sequence"])) for item in timeline]
        assert sequences == sorted(sequences)
        assert [item["eventType"] for item in timeline[:5]] == [
            "TELEMETRY_RECEIVED",
            "BREACH_POLICY_EVALUATED",
            "EVIDENCE_SNAPSHOT_CREATED",
            "RECOMMENDATION_CREATED",
            "GOVERNANCE_EVALUATED",
        ]
        for previous, current in pairwise(timeline):
            assert current["previousEventHash"] == previous["eventHash"]

        approval = ApprovalService(repository, SimulatedColdChainActionAdapter())
        with pytest.raises(AuthorizationError, match="own action"):
            await approval.decide(
                first.incident_id,
                UUID(recommendation_id),
                Identity(
                    DeterministicLocalRecommendationProvider.identity,
                    frozenset({"dispatcher"}),
                ),
                ApprovalDecision.APPROVED,
                "self approval",
                "integration-self-approval",
                event.correlation_id,
            )
        recommendation_uuid = UUID(recommendation_id)
        approval_key = f"integration-approved-{event.event_id}"
        approved = await approval.decide(
            first.incident_id,
            recommendation_uuid,
            Identity("dispatcher-integration", frozenset({"dispatcher"})),
            ApprovalDecision.APPROVED,
            "temperature evidence verified",
            approval_key,
            event.correlation_id,
        )
        replay = await approval.decide(
            first.incident_id,
            recommendation_uuid,
            Identity("dispatcher-integration", frozenset({"dispatcher"})),
            ApprovalDecision.APPROVED,
            "temperature evidence verified",
            approval_key,
            event.correlation_id,
        )
        assert approved["status"] == "SUCCEEDED"
        assert replay["idempotentReplay"] is True
        assert replay["approvalId"] == approved["approvalId"]
        assert replay["commandId"] == approved["commandId"]
        assert replay["actionResult"] == approved["actionResult"]
        with pytest.raises(WorkflowConflictError, match="conflicting input"):
            await approval.decide(
                first.incident_id,
                recommendation_uuid,
                Identity("dispatcher-integration", frozenset({"dispatcher"})),
                ApprovalDecision.APPROVED,
                "changed rationale",
                approval_key,
                event.correlation_id,
            )
        with pytest.raises(WorkflowConflictError, match="final human decision"):
            await approval.decide(
                first.incident_id,
                recommendation_uuid,
                Identity("dispatcher-integration", frozenset({"dispatcher"})),
                ApprovalDecision.REJECTED,
                "reverse approved decision",
                "integration-reject-after-approval",
                event.correlation_id,
            )
        command_id = UUID(str(approved["commandId"]))
        command = await repository.command_status(command_id)
        assert command is not None and command["status"] == "SUCCEEDED"
        assert command["actionResult"] == approved["actionResult"]
        completed = await repository.get_incident(first.incident_id)
        assert completed is not None
        assert completed["approval"]
        assert completed["command"]
        assert len(await repository.timeline(first.incident_id)) == 8
    finally:
        await database.dispose()


@pytest.mark.integration
async def test_guided_demo_incident_is_one_complete_preapproval_projection() -> None:
    database = Database(_url())
    repository = SqlWorkflowRepository(database)
    workflow = TemperatureBreachWorkflow(repository, DeterministicLocalRecommendationProvider())
    now = datetime.now(UTC)
    correlation_id = uuid4()
    shipment_id = uuid4()
    events = DemoScenarioService._events("sustained", now, correlation_id, shipment_id)
    try:
        before = len(await repository.list_incidents())
        results = [await workflow.process(event, now=now) for event in events]
        incident_id = results[-1].incident_id
        assert incident_id is not None
        assert len(await repository.list_incidents()) == before + 1

        incident = await repository.get_incident(incident_id)
        assert incident is not None
        assert str(incident["incidentReference"]).startswith("INC-DEMO-")
        assert str(incident["shipmentReference"]).startswith("CCS-DEMO-")
        assert str(incident_id) not in str(incident["incidentReference"])
        assert str(shipment_id) not in str(incident["shipmentReference"])
        assert incident["severity"] == "HIGH"
        assert incident["state"] == "AWAITING_APPROVAL"
        assert incident["sensorLabel"] == "Probe DEMO-01"
        assert incident["productLabel"] == "Synthetic fresh perishables"
        assert incident["route"] == {
            "origin": "Chicago, IL",
            "via": "Des Moines, IA",
            "destination": "Denver, CO",
            "progress": 55,
        }
        profile = incident["evidenceProfile"]
        assert isinstance(profile, dict)
        assert profile == {
            "sensorHealth": "Healthy",
            "calibration": "Verified",
            "sampleIntervalMinutes": 1,
            "readingQuality": "No quality flags",
            "productSensitivity": "High",
            "custodyVerification": "Complete",
            "complete": True,
        }
        telemetry = incident["telemetry"]
        assert isinstance(telemetry, list) and len(telemetry) == 3
        assert [item["temperatureCelsius"] for item in telemetry] == [8.7, 9.1, 9.4]
        assert all(item["policyInputs"]["upperThresholdCelsius"] == 8.0 for item in telemetry)
        assert all("lowerThresholdCelsius" not in item["policyInputs"] for item in telemetry)

        evidence = incident["evidence"]
        recommendation = incident["recommendation"]
        governance = incident["governance"]
        assert isinstance(evidence, dict)
        assert str(evidence["evidenceReference"]).startswith("EVD-DEMO-")
        assert str(evidence["evidenceId"]) not in str(evidence["evidenceReference"])
        assert isinstance(recommendation, dict)
        assert isinstance(governance, dict)
        cited = set(recommendation["provenance"]["citedChunkIds"])
        assert cited == {item["chunkId"] for item in incident["sopEvidence"]}
        applicability = {
            item["documentTitle"]: item["whyApplicable"] for item in incident["sopEvidence"]
        }
        assert applicability == {
            "Fresh and Perishable Temperature Excursions": (
                "This section defines how to respond to a sustained fresh-product temperature "
                "breach and requires preserving the shipment pending review."
            ),
            "Evidence and Sensor Integrity": (
                "This section defines the telemetry, sensor, timing, sequence, and integrity "
                "evidence required before a decision."
            ),
            "Shipment Hold, Inspection, and Release": (
                "This section requires authenticated dispatcher authorization for HOLD_SHIPMENT "
                "and prevents the recommendation engine from executing it directly."
            ),
        }
        assert len(set(applicability.values())) == 3
        assert recommendation["evidenceIds"] == [evidence["evidenceId"]]
        assert governance["decision"] == "APPROVAL_REQUIRED"
        assert all(check["state"] in {"pass", "warning"} for check in governance["checks"])
        assert "approval" not in incident
        assert "command" not in incident

        timeline = await repository.timeline(incident_id)
        assert [item["eventType"] for item in timeline] == [
            "TELEMETRY_RECEIVED",
            "BREACH_POLICY_EVALUATED",
            "EVIDENCE_SNAPSHOT_CREATED",
            "RECOMMENDATION_CREATED",
            "GOVERNANCE_EVALUATED",
        ]
        duplicate = await workflow.process(events[-1], now=now)
        assert duplicate.duplicate is True
        assert len(await repository.timeline(incident_id)) == 5
        assert len(await repository.list_incidents()) == before + 1
    finally:
        await database.dispose()


@pytest.mark.integration
async def test_expired_recommendation_fails_closed_and_audit_is_append_only() -> None:
    database = Database(_url())
    repository = SqlWorkflowRepository(database)
    event = _event()
    try:
        result = await TemperatureBreachWorkflow(
            repository, DeterministicLocalRecommendationProvider()
        ).process(event)
        assert result.incident_id is not None
        incident = await repository.get_incident(result.incident_id)
        assert incident is not None
        recommendation_id = UUID(str(incident["recommendationId"]))
        async with database.transaction() as session:
            await session.execute(
                update(RecommendationRecord)
                .where(RecommendationRecord.recommendation_id == recommendation_id)
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
        expired_view = await repository.get_incident(result.incident_id)
        assert expired_view is not None
        assert expired_view["recommendation"]["actionability"] == {
            "state": "EXPIRED",
            "approvalAllowed": False,
            "rejectionAllowed": False,
            "status": "Expired — approval blocked",
            "explanation": (
                "The historical governance evaluation remains unchanged, but a new human "
                "decision cannot be recorded after recommendation expiry."
            ),
            "expiresInMinutes": 0,
        }
        expiry_check = next(
            check
            for check in expired_view["governance"]["checks"]
            if check["name"] == "Expiry check"
        )
        assert expiry_check == {
            "name": "Expiry check",
            "state": "pass",
            "detail": "The recommendation was current when governance evaluated it.",
        }
        assert expired_view["governance"]["decision"] == "APPROVAL_REQUIRED"
        baseline_timeline = await repository.timeline(result.incident_id)
        service = ApprovalService(repository, SimulatedColdChainActionAdapter())
        identity = Identity("dispatcher-expiry", frozenset({"dispatcher"}))
        for decision, key in (
            (ApprovalDecision.APPROVED, "integration-expired-approval"),
            (ApprovalDecision.REJECTED, "integration-expired-rejection"),
        ):
            with pytest.raises(WorkflowConflictError, match="expired"):
                await service.decide(
                    result.incident_id,
                    recommendation_id,
                    identity,
                    decision,
                    "late decision",
                    key,
                    event.correlation_id,
                )
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.transaction() as session:
                sequence = await session.scalar(
                    select(func.min(AuditEventRecord.sequence)).where(
                        AuditEventRecord.incident_id == result.incident_id
                    )
                )
                await session.execute(
                    update(AuditEventRecord)
                    .where(AuditEventRecord.sequence == sequence)
                    .values(event_type="MUTATED")
                )
        async with database.transaction() as session:
            state = await session.scalar(
                select(IncidentRecord.state).where(IncidentRecord.incident_id == result.incident_id)
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ApprovalRecord)
                    .where(ApprovalRecord.recommendation_id == recommendation_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CommandRecord)
                    .where(CommandRecord.incident_id == result.incident_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ActionResultRecord)
                    .join(CommandRecord)
                    .where(CommandRecord.incident_id == result.incident_id)
                )
                == 0
            )
        assert state == "AWAITING_APPROVAL"
        assert await repository.timeline(result.incident_id) == baseline_timeline
    finally:
        await database.dispose()


@pytest.mark.integration
async def test_rejection_is_idempotent_and_cannot_be_reversed() -> None:
    database = Database(_url())
    repository = SqlWorkflowRepository(database)
    event = _event()
    try:
        result = await TemperatureBreachWorkflow(
            repository, DeterministicLocalRecommendationProvider()
        ).process(event)
        assert result.incident_id is not None
        incident = await repository.get_incident(result.incident_id)
        assert incident is not None
        recommendation_id = UUID(str(incident["recommendationId"]))
        service = ApprovalService(repository, SimulatedColdChainActionAdapter())
        identity = Identity("dispatcher-rejection", frozenset({"dispatcher"}))
        rejection_key = f"integration-rejected-{event.event_id}"
        rejected = await service.decide(
            result.incident_id,
            recommendation_id,
            identity,
            ApprovalDecision.REJECTED,
            "shipment must remain stopped",
            rejection_key,
            event.correlation_id,
        )
        replay = await service.decide(
            result.incident_id,
            recommendation_id,
            identity,
            ApprovalDecision.REJECTED,
            "shipment must remain stopped",
            rejection_key,
            event.correlation_id,
        )
        assert replay["approvalId"] == rejected["approvalId"]
        assert replay["idempotentReplay"] is True
        assert "commandId" not in replay
        assert len(await repository.timeline(result.incident_id)) == 6
        with pytest.raises(WorkflowConflictError, match="final human decision"):
            await service.decide(
                result.incident_id,
                recommendation_id,
                identity,
                ApprovalDecision.APPROVED,
                "attempt to reverse rejection",
                "integration-approve-after-rejection",
                event.correlation_id,
            )
    finally:
        await database.dispose()


@pytest.mark.integration
async def test_concurrent_duplicate_approval_converges_on_one_action_result() -> None:
    database = Database(_url())
    repository = SqlWorkflowRepository(database)
    event = _event()
    try:
        result = await TemperatureBreachWorkflow(
            repository, DeterministicLocalRecommendationProvider()
        ).process(event)
        assert result.incident_id is not None
        incident = await repository.get_incident(result.incident_id)
        assert incident is not None
        recommendation_id = UUID(str(incident["recommendationId"]))
        service = ApprovalService(repository, SimulatedColdChainActionAdapter())
        concurrent_key = f"integration-concurrent-{event.event_id}"
        request = (
            result.incident_id,
            recommendation_id,
            Identity("dispatcher-concurrent", frozenset({"dispatcher"})),
            ApprovalDecision.APPROVED,
            "concurrent evidence review",
            concurrent_key,
            event.correlation_id,
        )
        first, second = await asyncio.gather(service.decide(*request), service.decide(*request))
        assert first["approvalId"] == second["approvalId"]
        assert first["commandId"] == second["commandId"]
        assert first["actionResult"] == second["actionResult"]
        assert {first["idempotentReplay"], second["idempotentReplay"]} == {False, True}
        assert len(await repository.timeline(result.incident_id)) == 8
    finally:
        await database.dispose()
