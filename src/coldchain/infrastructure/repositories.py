"""Transactional SQLAlchemy repository for the governed workflow."""

import hashlib
import json
from datetime import UTC
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from coldchain.application.interfaces import Identity, ProcessingResult, WorkflowRepository
from coldchain.application.workflow import AuthorizationError, WorkflowConflictError
from coldchain.contracts.models import TelemetryEvent
from coldchain.domain import (
    ActionResult,
    ApprovalDecision,
    BreachEvaluation,
    Command,
    EvidenceSnapshot,
    GovernanceEvaluation,
    Incident,
    IncidentState,
    Recommendation,
    TemperatureReading,
    transition,
)
from coldchain.domain.incidents import utc_now
from coldchain.infrastructure.database import Database
from coldchain.infrastructure.models import (
    ActionResultRecord,
    ApprovalRecord,
    AuditEventRecord,
    CommandRecord,
    EvidenceRecord,
    GovernanceRecord,
    IncidentRecord,
    RecommendationRecord,
    TelemetryRecord,
)


class SqlWorkflowRepository(WorkflowRepository):
    component_version = "sql-workflow-repository-1.0"

    def __init__(self, database: Database) -> None:
        self._database = database

    async def recent_readings(
        self, shipment_id: UUID, limit: int
    ) -> tuple[TemperatureReading, ...]:
        async with self._database.transaction() as session:
            rows = (
                await session.scalars(
                    select(TelemetryRecord)
                    .where(TelemetryRecord.shipment_id == shipment_id)
                    .order_by(TelemetryRecord.reading_sequence.desc())
                    .limit(limit)
                )
            ).all()
        return tuple(
            TemperatureReading(
                event_id=row.event_id,
                occurred_at=row.occurred_at,
                sequence=row.reading_sequence,
                temperature_celsius=row.temperature_celsius,
            )
            for row in reversed(rows)
        )

    async def persist_telemetry_result(
        self,
        event: TelemetryEvent,
        evaluation: BreachEvaluation,
        incident: Incident | None,
        evidence: EvidenceSnapshot | None,
        recommendation: Recommendation | None,
        governance: GovernanceEvaluation | None,
    ) -> ProcessingResult:
        async with self._database.transaction() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:event_id, 0))"),
                {"event_id": str(event.event_id)},
            )
            existing = await session.get(TelemetryRecord, event.event_id)
            if existing is not None:
                return ProcessingResult(True, existing.disposition, None)
            session.add(
                TelemetryRecord(
                    event_id=event.event_id,
                    shipment_id=event.shipment_id,
                    correlation_id=event.correlation_id,
                    occurred_at=event.occurred_at,
                    reading_sequence=event.reading_sequence,
                    temperature_celsius=event.temperature_celsius,
                    cargo_type=event.cargo_type,
                    disposition=evaluation.disposition.value,
                    policy_version=evaluation.policy_version,
                    policy_inputs=evaluation.inputs,
                    reason_codes=list(evaluation.reason_codes),
                )
            )
            if incident is None or evidence is None or recommendation is None or governance is None:
                return ProcessingResult(False, evaluation.disposition.value, None)
            session.add(
                IncidentRecord(
                    incident_id=incident.incident_id,
                    shipment_id=incident.shipment_id,
                    state=incident.state.value,
                    severity=incident.severity,
                    policy_version=incident.policy_version,
                    source_event_ids=[str(item) for item in incident.source_event_ids],
                    correlation_id=incident.correlation_id,
                    created_at=incident.created_at,
                    updated_at=incident.created_at,
                )
            )
            await session.flush()
            session.add(
                EvidenceRecord(
                    evidence_id=evidence.evidence_id,
                    incident_id=evidence.incident_id,
                    telemetry_event_ids=[str(item) for item in evidence.telemetry_event_ids],
                    policy_inputs=evidence.policy_inputs,
                    summary=evidence.summary,
                    content_hash=evidence.content_hash,
                    captured_at=evidence.captured_at,
                )
            )
            session.add(
                RecommendationRecord(
                    recommendation_id=recommendation.recommendation_id,
                    incident_id=recommendation.incident_id,
                    evidence_ids=[str(item) for item in recommendation.evidence_ids],
                    action_type=recommendation.action_type,
                    parameters=recommendation.parameters,
                    provider=recommendation.provider,
                    author_identity=recommendation.author_identity,
                    rationale=recommendation.rationale,
                    expires_at=recommendation.expires_at,
                    non_authoritative=recommendation.non_authoritative,
                    provenance=recommendation.provenance or {},
                )
            )
            await session.flush()
            session.add(
                GovernanceRecord(
                    evaluation_id=governance.evaluation_id,
                    incident_id=governance.incident_id,
                    recommendation_id=governance.recommendation_id,
                    decision=governance.decision,
                    policy_version=governance.policy_version,
                    reason_codes=list(governance.reason_codes),
                    inputs=governance.inputs,
                    evaluated_at=governance.evaluated_at,
                )
            )
            await session.flush()
            audit_items: list[tuple[str, UUID | None, dict[str, Any]]] = [
                (
                    "TELEMETRY_RECEIVED",
                    event.event_id,
                    event.model_dump(mode="json", by_alias=True),
                ),
                (
                    "BREACH_POLICY_EVALUATED",
                    event.event_id,
                    {
                        "policyVersion": evaluation.policy_version,
                        "inputs": evaluation.inputs,
                        "reasonCodes": list(evaluation.reason_codes),
                        "outcome": evaluation.disposition.value,
                    },
                ),
                (
                    "EVIDENCE_SNAPSHOT_CREATED",
                    event.event_id,
                    {
                        "evidenceId": str(evidence.evidence_id),
                        "contentHash": evidence.content_hash,
                        "summary": evidence.summary,
                    },
                ),
                (
                    "RECOMMENDATION_CREATED",
                    evidence.evidence_id,
                    {
                        "recommendationId": str(recommendation.recommendation_id),
                        "provider": recommendation.provider,
                        "authorIdentity": recommendation.author_identity,
                        "actionType": recommendation.action_type,
                        "expiresAt": recommendation.expires_at.isoformat(),
                        "nonAuthoritative": recommendation.non_authoritative,
                        "provenance": recommendation.provenance or {},
                    },
                ),
                (
                    "GOVERNANCE_EVALUATED",
                    recommendation.recommendation_id,
                    {
                        "evaluationId": str(governance.evaluation_id),
                        "decision": governance.decision,
                        "policyVersion": governance.policy_version,
                        "reasonCodes": list(governance.reason_codes),
                        "inputs": governance.inputs,
                    },
                ),
            ]
            for event_type, causation_id, payload in audit_items:
                await self._append_audit(
                    session,
                    incident.incident_id,
                    event_type,
                    "service:temperature-breach-worker",
                    incident.correlation_id,
                    causation_id,
                    payload,
                )
            return ProcessingResult(False, evaluation.disposition.value, incident.incident_id)

    async def list_incidents(self) -> list[dict[str, object]]:
        async with self._database.transaction() as session:
            rows = (
                await session.scalars(
                    select(IncidentRecord).order_by(IncidentRecord.created_at.desc())
                )
            ).all()
            return [await self._incident_view(session, row) for row in rows]

    async def get_incident(self, incident_id: UUID) -> dict[str, object] | None:
        async with self._database.transaction() as session:
            row = await session.get(IncidentRecord, incident_id)
            if row is None:
                return None
            return await self._incident_view(session, row)

    async def demo_run_status(
        self, correlation_id: UUID, event_ids: tuple[UUID, ...]
    ) -> dict[str, object]:
        async with self._database.transaction() as session:
            telemetry = (
                await session.scalars(
                    select(TelemetryRecord)
                    .where(TelemetryRecord.event_id.in_(event_ids))
                    .order_by(TelemetryRecord.reading_sequence)
                )
            ).all()
            incident = await session.scalar(
                select(IncidentRecord)
                .where(IncidentRecord.correlation_id == correlation_id)
                .order_by(IncidentRecord.created_at.desc())
            )
            return {
                "processedEventCount": len(telemetry),
                "dispositions": [row.disposition for row in telemetry],
                "incident": await self._incident_view(session, incident) if incident else None,
            }

    async def timeline(self, incident_id: UUID) -> list[dict[str, object]]:
        async with self._database.transaction() as session:
            rows = (
                await session.scalars(
                    select(AuditEventRecord)
                    .where(AuditEventRecord.incident_id == incident_id)
                    .order_by(AuditEventRecord.sequence)
                )
            ).all()
            return [
                {
                    "sequence": row.sequence,
                    "auditEventId": str(row.audit_event_id),
                    "eventType": row.event_type,
                    "actorId": row.actor_id,
                    "correlationId": str(row.correlation_id),
                    "causationId": str(row.causation_id) if row.causation_id else None,
                    "componentVersion": row.component_version,
                    "schemaVersion": row.schema_version,
                    "payload": row.payload,
                    "occurredAt": row.occurred_at.isoformat(),
                    "previousEventHash": row.previous_event_hash,
                    "eventHash": row.event_hash,
                }
                for row in rows
            ]

    async def decide(
        self,
        incident_id: UUID,
        recommendation_id: UUID,
        identity: Identity,
        decision: ApprovalDecision,
        rationale: str,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> tuple[Command | None, dict[str, object]]:
        async with self._database.transaction() as session:
            if len(idempotency_key) < 16:
                raise WorkflowConflictError("idempotency key must contain at least 16 characters")
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": idempotency_key},
            )
            incident = await session.get(IncidentRecord, incident_id, with_for_update=True)
            recommendation = await session.get(RecommendationRecord, recommendation_id)
            if (
                incident is None
                or recommendation is None
                or recommendation.incident_id != incident_id
            ):
                raise WorkflowConflictError("incident or recommendation was not found")
            if identity.actor_id == recommendation.author_identity:
                raise AuthorizationError("recommendation authors cannot approve their own action")
            approval_id = uuid5(NAMESPACE_URL, f"coldchain-approval:{idempotency_key}")
            keyed_approval = await session.get(ApprovalRecord, approval_id)
            if keyed_approval is not None:
                if (
                    keyed_approval.incident_id != incident_id
                    or keyed_approval.recommendation_id != recommendation_id
                    or keyed_approval.actor_id != identity.actor_id
                    or keyed_approval.decision != decision.value
                    or keyed_approval.rationale != rationale
                ):
                    raise WorkflowConflictError(
                        "idempotency key was already used with conflicting input"
                    )
                return await self._existing_decision(session, keyed_approval)
            existing_decision = await session.scalar(
                select(ApprovalRecord).where(ApprovalRecord.recommendation_id == recommendation_id)
            )
            if existing_decision is not None:
                raise WorkflowConflictError("recommendation already has a final human decision")
            if recommendation.expires_at <= utc_now():
                raise WorkflowConflictError("recommendation has expired")
            governance = await session.scalar(
                select(GovernanceRecord).where(
                    GovernanceRecord.recommendation_id == recommendation_id
                )
            )
            if governance is None or governance.decision != "APPROVAL_REQUIRED":
                raise WorkflowConflictError("governance does not permit dispatcher approval")
            if IncidentState(incident.state) is not IncidentState.AWAITING_APPROVAL:
                raise WorkflowConflictError("incident is not awaiting approval")
            decided_at = utc_now()
            session.add(
                ApprovalRecord(
                    approval_id=approval_id,
                    incident_id=incident_id,
                    recommendation_id=recommendation_id,
                    actor_id=identity.actor_id,
                    actor_role="dispatcher",
                    decision=decision.value,
                    rationale=rationale,
                    decided_at=decided_at,
                )
            )
            await session.flush()
            target = (
                IncidentState.APPROVED
                if decision is ApprovalDecision.APPROVED
                else IncidentState.REJECTED
            )
            incident.state = transition(IncidentState(incident.state), target).value
            incident.updated_at = decided_at
            await self._append_audit(
                session,
                incident_id,
                "HUMAN_DECISION_RECORDED",
                identity.actor_id,
                correlation_id,
                recommendation_id,
                {
                    "approvalId": str(approval_id),
                    "decision": decision.value,
                    "actorRole": "dispatcher",
                    "rationale": rationale,
                },
            )
            response: dict[str, object] = {
                "approvalId": str(approval_id),
                "decision": decision.value,
                "idempotentReplay": False,
            }
            if decision is ApprovalDecision.REJECTED:
                return None, response
            command = Command(
                command_id=uuid4(),
                incident_id=incident_id,
                recommendation_id=recommendation_id,
                approval_id=approval_id,
                action_type=recommendation.action_type,
                parameters=recommendation.parameters,
                idempotency_key=idempotency_key,
                created_at=decided_at,
            )
            session.add(
                CommandRecord(
                    command_id=command.command_id,
                    incident_id=command.incident_id,
                    recommendation_id=command.recommendation_id,
                    approval_id=command.approval_id,
                    action_type=command.action_type,
                    parameters=command.parameters,
                    idempotency_key=command.idempotency_key,
                    status="PENDING",
                    created_at=command.created_at,
                )
            )
            incident.state = transition(
                IncidentState(incident.state), IncidentState.EXECUTING
            ).value
            await self._append_audit(
                session,
                incident_id,
                "COMMAND_CREATED",
                "service:approval-control-plane",
                correlation_id,
                approval_id,
                {
                    "commandId": str(command.command_id),
                    "actionType": command.action_type,
                    "idempotencyKey": command.idempotency_key,
                },
            )
            return command, response

    async def complete_command(self, command: Command, result: ActionResult) -> ActionResult:
        async with self._database.transaction() as session:
            command_row = await session.get(CommandRecord, command.command_id, with_for_update=True)
            if command_row is None:
                raise WorkflowConflictError("command was not found")
            existing = await session.scalar(
                select(ActionResultRecord).where(
                    ActionResultRecord.command_id == command.command_id
                )
            )
            if existing is not None:
                return self._action_result(existing)
            incident = await session.get(IncidentRecord, command.incident_id, with_for_update=True)
            if incident is None:
                raise WorkflowConflictError("incident was not found")
            session.add(
                ActionResultRecord(
                    result_id=result.result_id,
                    command_id=result.command_id,
                    status=result.status,
                    adapter=result.adapter,
                    detail=result.detail,
                    completed_at=result.completed_at,
                )
            )
            command_row.status = result.status
            target = (
                IncidentState.RESOLVED if result.status == "SUCCEEDED" else IncidentState.FAILED
            )
            incident.state = transition(IncidentState(incident.state), target).value
            incident.updated_at = result.completed_at
            await self._append_audit(
                session,
                command.incident_id,
                "SIMULATED_ACTION_COMPLETED",
                result.adapter,
                incident.correlation_id,
                command.command_id,
                {
                    "resultId": str(result.result_id),
                    "commandId": str(command.command_id),
                    "status": result.status,
                    "detail": result.detail,
                },
            )
            return result

    async def command_status(self, command_id: UUID) -> dict[str, object] | None:
        async with self._database.transaction() as session:
            command = await session.get(CommandRecord, command_id)
            if command is None:
                return None
            result = await session.scalar(
                select(ActionResultRecord).where(ActionResultRecord.command_id == command_id)
            )
            return {
                "commandId": str(command.command_id),
                "incidentId": str(command.incident_id),
                "actionType": command.action_type,
                "status": result.status if result else command.status,
                "adapter": result.adapter if result else None,
                "detail": result.detail if result else None,
                "actionResult": (
                    {
                        "resultId": str(result.result_id),
                        "status": result.status,
                        "adapter": result.adapter,
                        "detail": result.detail,
                        "completedAt": result.completed_at.astimezone(UTC).isoformat(),
                    }
                    if result
                    else None
                ),
            }

    async def _append_audit(
        self,
        session: AsyncSession,
        incident_id: UUID,
        event_type: str,
        actor_id: str,
        correlation_id: UUID,
        causation_id: UUID | None,
        payload: dict[str, Any],
    ) -> None:
        previous_hash = await session.scalar(
            select(AuditEventRecord.event_hash)
            .where(AuditEventRecord.incident_id == incident_id)
            .order_by(AuditEventRecord.sequence.desc())
            .limit(1)
        )
        occurred_at = utc_now()
        audit_event_id = uuid4()
        canonical = json.dumps(
            {
                "auditEventId": str(audit_event_id),
                "incidentId": str(incident_id),
                "eventType": event_type,
                "actorId": actor_id,
                "correlationId": str(correlation_id),
                "causationId": str(causation_id) if causation_id else None,
                "payload": payload,
                "occurredAt": occurred_at.isoformat(),
                "previousEventHash": previous_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        event_hash = hashlib.sha256(canonical.encode()).hexdigest()
        session.add(
            AuditEventRecord(
                audit_event_id=audit_event_id,
                incident_id=incident_id,
                event_type=event_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                component_version=self.component_version,
                schema_version="1.0",
                payload=payload,
                occurred_at=occurred_at,
                previous_event_hash=previous_hash,
                event_hash=event_hash,
            )
        )
        await session.flush()

    @staticmethod
    def _incident_dict(row: IncidentRecord) -> dict[str, object]:
        return {
            "incidentId": str(row.incident_id),
            "shipmentId": str(row.shipment_id),
            "state": row.state,
            "severity": row.severity,
            "policyVersion": row.policy_version,
            "sourceEventIds": row.source_event_ids,
            "correlationId": str(row.correlation_id),
            "createdAt": row.created_at.astimezone(UTC).isoformat(),
            "updatedAt": row.updated_at.astimezone(UTC).isoformat(),
        }

    async def _incident_view(self, session: AsyncSession, row: IncidentRecord) -> dict[str, object]:
        result = self._incident_dict(row)
        telemetry = (
            await session.scalars(
                select(TelemetryRecord)
                .where(TelemetryRecord.event_id.in_([UUID(item) for item in row.source_event_ids]))
                .order_by(TelemetryRecord.reading_sequence)
            )
        ).all()
        # Include prior readings from the same shipment so sustained-breach evidence is visible.
        if telemetry:
            telemetry = (
                await session.scalars(
                    select(TelemetryRecord)
                    .where(TelemetryRecord.shipment_id == row.shipment_id)
                    .order_by(TelemetryRecord.reading_sequence.desc())
                    .limit(20)
                )
            ).all()[::-1]
        result["telemetry"] = [
            {
                "eventId": str(item.event_id),
                "occurredAt": item.occurred_at.astimezone(UTC).isoformat(),
                "readingSequence": item.reading_sequence,
                "temperatureCelsius": item.temperature_celsius,
                "cargoType": item.cargo_type,
                "disposition": item.disposition,
                "policyInputs": item.policy_inputs,
                "reasonCodes": item.reason_codes,
            }
            for item in telemetry
        ]
        evidence = await session.scalar(
            select(EvidenceRecord).where(EvidenceRecord.incident_id == row.incident_id)
        )
        if evidence is not None:
            result["evidence"] = {
                "evidenceId": str(evidence.evidence_id),
                "telemetryEventIds": evidence.telemetry_event_ids,
                "policyInputs": evidence.policy_inputs,
                "summary": evidence.summary,
                "contentHash": evidence.content_hash,
                "capturedAt": evidence.captured_at.astimezone(UTC).isoformat(),
            }
        recommendation = await session.scalar(
            select(RecommendationRecord).where(RecommendationRecord.incident_id == row.incident_id)
        )
        if recommendation is not None:
            result.update(
                {
                    "recommendationId": str(recommendation.recommendation_id),
                    "recommendedAction": recommendation.action_type,
                    "recommendationExpiresAt": recommendation.expires_at.isoformat(),
                    "recommendationProvenance": recommendation.provenance,
                    "recommendation": {
                        "recommendationId": str(recommendation.recommendation_id),
                        "evidenceIds": recommendation.evidence_ids,
                        "actionType": recommendation.action_type,
                        "parameters": recommendation.parameters,
                        "provider": recommendation.provider,
                        "authorIdentity": recommendation.author_identity,
                        "rationale": recommendation.rationale,
                        "expiresAt": recommendation.expires_at.astimezone(UTC).isoformat(),
                        "nonAuthoritative": recommendation.non_authoritative,
                        "provenance": recommendation.provenance,
                    },
                }
            )
            governance = await session.scalar(
                select(GovernanceRecord).where(
                    GovernanceRecord.recommendation_id == recommendation.recommendation_id
                )
            )
            if governance is not None:
                result["governance"] = {
                    "evaluationId": str(governance.evaluation_id),
                    "recommendationId": str(governance.recommendation_id),
                    "decision": governance.decision,
                    "policyVersion": governance.policy_version,
                    "reasonCodes": governance.reason_codes,
                    "inputs": governance.inputs,
                    "evaluatedAt": governance.evaluated_at.astimezone(UTC).isoformat(),
                }
            approval = await session.scalar(
                select(ApprovalRecord).where(
                    ApprovalRecord.recommendation_id == recommendation.recommendation_id
                )
            )
            if approval is not None:
                result["approval"] = {
                    "approvalId": str(approval.approval_id),
                    "recommendationId": str(approval.recommendation_id),
                    "actorId": approval.actor_id,
                    "actorRole": approval.actor_role,
                    "decision": approval.decision,
                    "rationale": approval.rationale,
                    "decidedAt": approval.decided_at.astimezone(UTC).isoformat(),
                }
                command = await session.scalar(
                    select(CommandRecord).where(CommandRecord.approval_id == approval.approval_id)
                )
                if command is not None:
                    action_result = await session.scalar(
                        select(ActionResultRecord).where(
                            ActionResultRecord.command_id == command.command_id
                        )
                    )
                    result["command"] = {
                        "commandId": str(command.command_id),
                        "incidentId": str(command.incident_id),
                        "actionType": command.action_type,
                        "status": action_result.status if action_result else command.status,
                        "adapter": action_result.adapter if action_result else None,
                        "detail": action_result.detail if action_result else None,
                        "actionResult": (
                            {
                                "resultId": str(action_result.result_id),
                                "status": action_result.status,
                                "adapter": action_result.adapter,
                                "detail": action_result.detail,
                                "completedAt": action_result.completed_at.astimezone(
                                    UTC
                                ).isoformat(),
                            }
                            if action_result
                            else None
                        ),
                    }
        return result

    @staticmethod
    def _command(row: CommandRecord) -> Command:
        return Command(
            command_id=row.command_id,
            incident_id=row.incident_id,
            recommendation_id=row.recommendation_id,
            approval_id=row.approval_id,
            action_type=row.action_type,
            parameters=row.parameters,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
        )

    async def _existing_decision(
        self, session: AsyncSession, approval: ApprovalRecord
    ) -> tuple[Command | None, dict[str, object]]:
        command = await session.scalar(
            select(CommandRecord).where(CommandRecord.approval_id == approval.approval_id)
        )
        response: dict[str, object] = {
            "approvalId": str(approval.approval_id),
            "decision": approval.decision,
            "idempotentReplay": True,
        }
        if command is None:
            return None, response
        result = await session.scalar(
            select(ActionResultRecord).where(ActionResultRecord.command_id == command.command_id)
        )
        response["commandId"] = str(command.command_id)
        response["status"] = result.status if result is not None else command.status
        if result is not None:
            response["actionResult"] = {
                "resultId": str(result.result_id),
                "status": result.status,
                "adapter": result.adapter,
                "detail": result.detail,
                "completedAt": result.completed_at.isoformat(),
            }
            return None, response
        # A prior request may have committed the command and then stopped before
        # recording its result. Reuse that command through the idempotent action
        # adapter so retries and concurrent duplicates converge on one result.
        return self._command(command), response

    @staticmethod
    def _action_result(row: ActionResultRecord) -> ActionResult:
        return ActionResult(
            result_id=row.result_id,
            command_id=row.command_id,
            status=row.status,
            adapter=row.adapter,
            detail=row.detail,
            completed_at=row.completed_at,
        )
