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
    Recommendation,
    TemperatureReading,
    transition,
)
from coldchain.domain.governance import ActionRequest, GovernanceDecision, GovernancePolicy
from coldchain.domain.incidents import utc_now
from coldchain.governance.engine import DeterministicGovernanceEngine
from coldchain.observability.metrics import bounded, metrics
from coldchain.observability.tracing import span


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
        with span("policy.evaluate", attributes={"coldchain.component": "policy"}):
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
            with span("persistence.telemetry", attributes={"coldchain.outcome": "no_breach"}):
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
        metrics.incidents_created.labels(
            breach_type="temperature",
            severity=bounded(incident.severity, {"LOW", "MEDIUM", "HIGH", "CRITICAL"}),
        ).inc()
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
        with span("recommendation.generate", attributes={"coldchain.component": "recommendation"}):
            recommendation = self._provider.recommend(incident, evidence)
        with span("governance.evaluate", attributes={"coldchain.component": "governance"}):
            governance = self._evaluate_governance(incident, evidence, recommendation, evaluated_at)
        target_state = (
            IncidentState.AWAITING_APPROVAL
            if governance.decision == GovernanceDecision.APPROVAL_REQUIRED.value
            else IncidentState.FAILED
        )
        incident = replace(incident, state=transition(incident.state, target_state))
        metrics.incidents_current.labels(state=target_state.value.lower()).inc()
        metrics.governance_decisions.labels(
            decision=bounded(governance.decision, {"ALLOWED", "APPROVAL_REQUIRED", "PROHIBITED"})
        ).inc()
        if governance.decision == GovernanceDecision.PROHIBITED.value:
            metrics.governance_fail_closed.labels(reason="prohibited").inc()
        with span("persistence.incident", attributes={"coldchain.outcome": "created"}):
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
            metrics.recommendations_expired.inc()
            reason_codes = ("RECOMMENDATION_EXPIRED",)
        elif not recommendation.non_authoritative:
            reason_codes = ("AUTHORITATIVE_RECOMMENDATION_REJECTED",)
        elif (
            recommendation.provenance
            and recommendation.provenance.get("api_family") == "openai-compatible"
            and self._ai_provenance_invalid(recommendation, evidence)
        ):
            reason_codes = ("AI_PROVENANCE_VALIDATION_FAILED",)
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
            if self._kill_switch_active:
                metrics.kill_switch_blocks.inc()
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

    @staticmethod
    def _ai_provenance_invalid(recommendation: Recommendation, evidence: EvidenceSnapshot) -> bool:
        provenance = recommendation.provenance or {}
        cited_chunks = set(provenance.get("cited_chunk_ids", []))
        retrieved_chunks = set(provenance.get("retrieved_chunk_ids", []))
        provider = str(provenance.get("provider", ""))
        return bool(
            provenance.get("validation_result") != "valid"
            or provenance.get("response_schema_version") != "1.0"
            or not provenance.get("evidence_sufficient")
            or not cited_chunks
            or not cited_chunks <= retrieved_chunks
            or str(evidence.evidence_id) not in provenance.get("cited_incident_evidence_ids", [])
            or not recommendation.provider.startswith(provider + ":")
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
        with span("approval.decide", attributes={"coldchain.component": "governance"}):
            if "dispatcher" not in identity.roles:
                metrics.approval_decisions.labels(decision="unauthorized").inc()
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
            metrics.approval_decisions.labels(decision=decision.value.lower()).inc()
            metrics.incidents_current.labels(state="awaiting_approval").dec()
            metrics.incidents_current.labels(state=decision.value.lower()).inc()
        if command is not None:
            action = bounded(command.action_type, {"HOLD_SHIPMENT", "ADD_NOTE"})
            metrics.commands_created.labels(action=action).inc()
            with span("command.execute", attributes={"coldchain.action": command.action_type}):
                result = await self._adapter.execute(command)
            metrics.simulated_actions.labels(outcome=result.status.lower()).inc()
            with span(
                "persistence.command",
                attributes={"coldchain.outcome": result.status.lower()},
            ):
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
