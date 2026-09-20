import asyncio
import os
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from coldchain.application.actions import SimulatedColdChainActionAdapter
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
from coldchain.infrastructure.models import AuditEventRecord, IncidentRecord, RecommendationRecord
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
        assert len(await repository.timeline(first.incident_id)) == 8
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
        with pytest.raises(WorkflowConflictError, match="expired"):
            await ApprovalService(repository, SimulatedColdChainActionAdapter()).decide(
                result.incident_id,
                recommendation_id,
                Identity("dispatcher-expiry", frozenset({"dispatcher"})),
                ApprovalDecision.APPROVED,
                "late decision",
                "integration-expired-approval",
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
        assert state == "AWAITING_APPROVAL"
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
