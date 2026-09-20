"""Application orchestration for detection, governance, approval, and execution."""

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

from coldchain.application.interfaces import (
    ActionAdapter,
    Identity,
    ProcessingResult,
    RecommendationProvider,
    WorkflowRepository,
)
from coldchain.contracts.models import TelemetryEvent
from coldchain.domain import (
    ApprovalDecision,
    BreachDisposition,
    EvidenceSnapshot,
    FreshPerishablePolicy,
    GovernanceEvaluation,
    Incident,
    IncidentState,
    TemperatureReading,
    transition,
)
from coldchain.domain.governance import ActionRequest, GovernanceDecision, GovernancePolicy
from coldchain.domain.incidents import utc_now
from coldchain.governance.engine import DeterministicGovernanceEngine


class AuthorizationError(PermissionError):
    pass


class WorkflowConflictError(RuntimeError):
    pass


class TemperatureBreachWorkflow:
    component_version = "temperature-breach-workflow-1.0"

    def __init__(
        self,
        repository: WorkflowRepository,
        recommendation_provider: RecommendationProvider,
        policy: FreshPerishablePolicy | None = None,
        kill_switch_active: bool = False,
    ) -> None:
        self._repository = repository
        self._provider = recommendation_provider
        self._policy = policy or FreshPerishablePolicy()
        self._kill_switch_active = kill_switch_active
        self._governance = DeterministicGovernanceEngine()

    async def process(self, event: TelemetryEvent, now: datetime | None = None) -> ProcessingResult:
        evaluated_at = now or utc_now()
        history = await self._repository.recent_readings(
            event.shipment_id, self._policy.sustained_reading_count - 1
        )
        reading = TemperatureReading(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            sequence=event.reading_sequence,
            temperature_celsius=event.temperature_celsius,
        )
        if event.cargo_type != "FRESH_PERISHABLES":
            evaluation = self._policy.fail_closed(
                {
                    "cargoType": event.cargo_type,
                    "temperatureCelsius": event.temperature_celsius,
                    "readingSequence": event.reading_sequence,
                },
                "UNSUPPORTED_CARGO_POLICY",
            )
        else:
            try:
                evaluation = self._policy.evaluate(reading, history, evaluated_at)
            except (ValueError, ArithmeticError):
                evaluation = self._policy.fail_closed(
                    {"eventId": str(event.event_id)}, "POLICY_EVALUATION_ERROR"
                )

        if evaluation.disposition is not BreachDisposition.BREACH:
            return await self._repository.persist_telemetry_result(
                event, evaluation, None, None, None, None
            )

        incident = Incident(
            incident_id=uuid4(),
            shipment_id=event.shipment_id,
            state=IncidentState.OPEN,
            severity=evaluation.severity or "HIGH",
            policy_version=evaluation.policy_version,
            source_event_ids=(event.event_id,),
            correlation_id=event.correlation_id,
            created_at=evaluated_at,
        )
        evidence_payload = {
            "eventId": str(event.event_id),
            "policyVersion": evaluation.policy_version,
            "inputs": evaluation.inputs,
            "reasonCodes": list(evaluation.reason_codes),
        }
        evidence = EvidenceSnapshot(
            evidence_id=uuid4(),
            incident_id=incident.incident_id,
            telemetry_event_ids=(event.event_id,),
            policy_inputs=evaluation.inputs,
            summary="Versioned telemetry evidence for deterministic temperature breach",
            content_hash=hashlib.sha256(
                json.dumps(evidence_payload, sort_keys=True).encode()
            ).hexdigest(),
            captured_at=evaluated_at,
        )
        incident = replace(
            incident,
            state=transition(incident.state, IncidentState.EVIDENCE_COLLECTED),
        )
        recommendation = self._provider.recommend(incident, evidence)
        governance = self._evaluate_governance(incident, evidence, recommendation, evaluated_at)
        target_state = (
            IncidentState.AWAITING_APPROVAL
            if governance.decision == GovernanceDecision.APPROVAL_REQUIRED.value
            else IncidentState.FAILED
        )
        incident = replace(incident, state=transition(incident.state, target_state))
        return await self._repository.persist_telemetry_result(
            event, evaluation, incident, evidence, recommendation, governance
        )

    def _evaluate_governance(
        self,
        incident: Incident,
        evidence: EvidenceSnapshot,
        recommendation: object,
        now: datetime,
    ) -> GovernanceEvaluation:
        from coldchain.domain import Recommendation

        reason_codes: tuple[str, ...]
        decision = GovernanceDecision.PROHIBITED
        if not isinstance(recommendation, Recommendation):
            reason_codes = ("UNKNOWN_RECOMMENDATION",)
        elif (
            not recommendation.evidence_ids
            or evidence.evidence_id not in recommendation.evidence_ids
        ):
            reason_codes = ("MISSING_EVIDENCE",)
        elif recommendation.expires_at <= now:
            reason_codes = ("RECOMMENDATION_EXPIRED",)
        elif not recommendation.non_authoritative:
            reason_codes = ("AUTHORITATIVE_RECOMMENDATION_REJECTED",)
        else:
            result = self._governance.evaluate(
                ActionRequest(recommendation.action_type),
                GovernancePolicy(
                    version="temperature-action-governance-1.0",
                    allowed_actions=frozenset({"ADD_NOTE"}),
                    approval_required_actions=frozenset({"HOLD_SHIPMENT"}),
                    prohibited_actions=frozenset({"DISABLE_REFRIGERATION"}),
                    kill_switch_active=self._kill_switch_active,
                ),
            )
            decision = result.decision
            reason_codes = (decision.value,)
        return GovernanceEvaluation(
            evaluation_id=uuid4(),
            incident_id=incident.incident_id,
            recommendation_id=(
                recommendation.recommendation_id
                if isinstance(recommendation, Recommendation)
                else uuid4()
            ),
            decision=decision.value,
            policy_version="temperature-action-governance-1.0",
            reason_codes=reason_codes,
            inputs={"evidenceId": str(evidence.evidence_id)},
            evaluated_at=now,
        )


class ApprovalService:
    def __init__(self, repository: WorkflowRepository, adapter: ActionAdapter) -> None:
        self._repository = repository
        self._adapter = adapter

    async def decide(
        self,
        incident_id: UUID,
        recommendation_id: UUID,
        identity: Identity,
        decision: ApprovalDecision,
        rationale: str,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> dict[str, object]:
        if "dispatcher" not in identity.roles:
            raise AuthorizationError("dispatcher role is required")
        command, response = await self._repository.decide(
            incident_id,
            recommendation_id,
            identity,
            decision,
            rationale,
            idempotency_key,
            correlation_id,
        )
        if command is not None:
            result = await self._adapter.execute(command)
            durable_result = await self._repository.complete_command(command, result)
            response = {
                **response,
                "commandId": str(command.command_id),
                "status": durable_result.status,
                "actionResult": {
                    "resultId": str(durable_result.result_id),
                    "status": durable_result.status,
                    "adapter": durable_result.adapter,
                    "detail": durable_result.detail,
                    "completedAt": durable_result.completed_at.isoformat(),
                },
            }
        return response
