from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from coldchain.application.actions import SimulatedColdChainActionAdapter
from coldchain.application.interfaces import Identity, ProcessingResult, WorkflowRepository
from coldchain.application.recommendations import DeterministicLocalRecommendationProvider
from coldchain.application.workflow import (
    ApprovalService,
    AuthorizationError,
    TemperatureBreachWorkflow,
)
from coldchain.contracts.models import TelemetryEvent
from coldchain.domain import (
    ActionResult,
    ApprovalDecision,
    BreachEvaluation,
    Command,
    EvidenceSnapshot,
    GovernanceEvaluation,
    Incident,
    Recommendation,
    TemperatureReading,
)
from coldchain.domain.breach import FreshPerishablePolicy
from coldchain.domain.incidents import utc_now


def telemetry(temperature: float = 10.5, sequence: int = 1) -> TelemetryEvent:
    return TelemetryEvent(
        event_id=uuid4(),
        correlation_id=uuid4(),
        occurred_at=utc_now(),
        producer="test",
        shipment_id=uuid4(),
        vehicle_id="vehicle-1",
        sensor_id="sensor-1",
        latitude=1,
        longitude=1,
        temperature_celsius=temperature,
        cargo_type="FRESH_PERISHABLES",
        reading_sequence=sequence,
    )


class FakeRepository(WorkflowRepository):
    def __init__(self) -> None:
        self.history: tuple[TemperatureReading, ...] = ()
        self.saved: tuple[Any, ...] | None = None
        self.command = Command(
            uuid4(), uuid4(), uuid4(), uuid4(), "HOLD_SHIPMENT", {}, "approval:key-12345", utc_now()
        )
        self.completed: ActionResult | None = None

    async def recent_readings(
        self, shipment_id: UUID, limit: int
    ) -> tuple[TemperatureReading, ...]:
        return self.history[-limit:]

    async def persist_telemetry_result(
        self,
        event: TelemetryEvent,
        evaluation: BreachEvaluation,
        incident: Incident | None,
        evidence: EvidenceSnapshot | None,
        recommendation: Recommendation | None,
        governance: GovernanceEvaluation | None,
    ) -> ProcessingResult:
        self.saved = (event, evaluation, incident, evidence, recommendation, governance)
        return ProcessingResult(
            False, evaluation.disposition.value, incident.incident_id if incident else None
        )

    async def list_incidents(self) -> list[dict[str, object]]:
        return []

    async def get_incident(self, incident_id: UUID) -> dict[str, object] | None:
        return None

    async def timeline(self, incident_id: UUID) -> list[dict[str, object]]:
        return []

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
        if decision is ApprovalDecision.REJECTED:
            return None, {"approvalId": str(uuid4()), "decision": decision.value}
        return self.command, {
            "approvalId": str(self.command.approval_id),
            "decision": decision.value,
        }

    async def complete_command(self, command: Command, result: ActionResult) -> ActionResult:
        self.completed = result
        return result

    async def command_status(self, command_id: UUID) -> dict[str, object] | None:
        return None


class ExpiredProvider(DeterministicLocalRecommendationProvider):
    def recommend(self, incident: Incident, evidence: EvidenceSnapshot) -> Recommendation:
        recommendation = super().recommend(incident, evidence)
        return Recommendation(
            recommendation.recommendation_id,
            recommendation.incident_id,
            recommendation.evidence_ids,
            recommendation.action_type,
            recommendation.parameters,
            recommendation.provider,
            recommendation.author_identity,
            recommendation.rationale,
            datetime.now(UTC) - timedelta(minutes=1),
        )


class BrokenPolicy(FreshPerishablePolicy):
    def evaluate(
        self,
        current: TemperatureReading,
        history: tuple[TemperatureReading, ...],
        evaluated_at: datetime,
    ) -> BreachEvaluation:
        raise ArithmeticError("policy failure")


async def test_breach_builds_evidence_recommendation_and_approval_governance() -> None:
    repository = FakeRepository()
    event = telemetry()
    result = await TemperatureBreachWorkflow(
        repository, DeterministicLocalRecommendationProvider()
    ).process(event)
    assert result.incident_id is not None
    assert repository.saved is not None
    evaluation, recommendation, governance = (
        repository.saved[1],
        repository.saved[4],
        repository.saved[5],
    )
    assert evaluation.reason_codes == ("CLEARLY_UNSAFE_TEMPERATURE",)
    assert recommendation.non_authoritative is True
    assert governance.decision == "APPROVAL_REQUIRED"


async def test_normal_and_unsupported_cargo_do_not_create_incidents() -> None:
    repository = FakeRepository()
    workflow = TemperatureBreachWorkflow(repository, DeterministicLocalRecommendationProvider())
    normal = await workflow.process(telemetry(5))
    event = telemetry(5)
    event = event.model_copy(update={"cargo_type": "FROZEN"})
    unsupported = await workflow.process(event)
    assert normal.incident_id is None
    assert unsupported.disposition == "FAIL_CLOSED"


async def test_expired_recommendation_fails_governance_closed() -> None:
    repository = FakeRepository()
    await TemperatureBreachWorkflow(repository, ExpiredProvider()).process(telemetry())
    assert repository.saved is not None
    governance = repository.saved[5]
    assert governance.decision == "PROHIBITED"
    assert governance.reason_codes == ("RECOMMENDATION_EXPIRED",)
    assert repository.saved[2].state.value == "FAILED"


async def test_kill_switch_fails_closed() -> None:
    repository = FakeRepository()
    workflow = TemperatureBreachWorkflow(
        repository,
        DeterministicLocalRecommendationProvider(),
        kill_switch_active=True,
    )
    await workflow.process(telemetry())
    assert repository.saved is not None
    assert repository.saved[5].decision == "KILL_SWITCH_ACTIVE"
    assert repository.saved[2].state.value == "FAILED"


async def test_policy_exception_fails_closed() -> None:
    repository = FakeRepository()
    workflow = TemperatureBreachWorkflow(
        repository, DeterministicLocalRecommendationProvider(), BrokenPolicy()
    )
    result = await workflow.process(telemetry())
    assert result.disposition == "FAIL_CLOSED"
    assert repository.saved is not None
    assert repository.saved[1].reason_codes == ("POLICY_EVALUATION_ERROR",)


async def test_governance_rejects_unknown_missing_evidence_and_authority_claims() -> None:
    repository = FakeRepository()
    workflow = TemperatureBreachWorkflow(repository, DeterministicLocalRecommendationProvider())
    await workflow.process(telemetry())
    assert repository.saved is not None
    incident = repository.saved[2]
    evidence = repository.saved[3]
    recommendation = repository.saved[4]
    assert isinstance(incident, Incident)
    assert isinstance(evidence, EvidenceSnapshot)
    assert isinstance(recommendation, Recommendation)
    unknown = workflow._evaluate_governance(incident, evidence, object(), utc_now())
    missing = workflow._evaluate_governance(
        incident,
        evidence,
        Recommendation(
            recommendation.recommendation_id,
            recommendation.incident_id,
            (uuid4(),),
            recommendation.action_type,
            recommendation.parameters,
            recommendation.provider,
            recommendation.author_identity,
            recommendation.rationale,
            recommendation.expires_at,
        ),
        utc_now(),
    )
    authoritative = workflow._evaluate_governance(
        incident,
        evidence,
        Recommendation(
            recommendation.recommendation_id,
            recommendation.incident_id,
            recommendation.evidence_ids,
            recommendation.action_type,
            recommendation.parameters,
            recommendation.provider,
            recommendation.author_identity,
            recommendation.rationale,
            recommendation.expires_at,
            non_authoritative=False,
        ),
        utc_now(),
    )
    assert unknown.reason_codes == ("UNKNOWN_RECOMMENDATION",)
    assert missing.reason_codes == ("MISSING_EVIDENCE",)
    assert authoritative.reason_codes == ("AUTHORITATIVE_RECOMMENDATION_REJECTED",)


async def test_approval_requires_dispatcher_and_execution_is_idempotent() -> None:
    repository = FakeRepository()
    adapter = SimulatedColdChainActionAdapter()
    service = ApprovalService(repository, adapter)
    with pytest.raises(AuthorizationError):
        await service.decide(
            uuid4(),
            uuid4(),
            Identity("viewer", frozenset({"viewer"})),
            ApprovalDecision.APPROVED,
            "ok",
            "approval-test-unauthorized",
            uuid4(),
        )
    response = await service.decide(
        uuid4(),
        uuid4(),
        Identity("dispatcher-1", frozenset({"dispatcher"})),
        ApprovalDecision.APPROVED,
        "verified",
        "approval-test-approved",
        uuid4(),
    )
    assert response["status"] == "SUCCEEDED"
    first = repository.completed
    assert first is not None
    action_result = cast(dict[str, object], response["actionResult"])
    assert action_result["resultId"] == str(first.result_id)
    assert await adapter.execute(repository.command) == first


async def test_rejection_creates_no_command() -> None:
    repository = FakeRepository()
    service = ApprovalService(repository, SimulatedColdChainActionAdapter())
    response = await service.decide(
        uuid4(),
        uuid4(),
        Identity("dispatcher-1", frozenset({"dispatcher"})),
        ApprovalDecision.REJECTED,
        "not safe",
        "approval-test-rejected",
        uuid4(),
    )
    assert response["decision"] == "REJECTED"
    assert repository.completed is None
