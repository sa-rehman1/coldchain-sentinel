"""Application ports for the temperature-breach vertical slice."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

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


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    duplicate: bool
    disposition: str
    incident_id: UUID | None


@dataclass(frozen=True, slots=True)
class Identity:
    actor_id: str
    roles: frozenset[str]


class RecommendationProvider(Protocol):
    identity: str

    def recommend(self, incident: Incident, evidence: EvidenceSnapshot) -> Recommendation: ...


class WorkflowRepository(Protocol):
    async def recent_readings(
        self, shipment_id: UUID, limit: int
    ) -> tuple[TemperatureReading, ...]: ...

    async def persist_telemetry_result(
        self,
        event: TelemetryEvent,
        evaluation: BreachEvaluation,
        incident: Incident | None,
        evidence: EvidenceSnapshot | None,
        recommendation: Recommendation | None,
        governance: GovernanceEvaluation | None,
    ) -> ProcessingResult: ...

    async def list_incidents(self) -> list[dict[str, object]]: ...

    async def get_incident(self, incident_id: UUID) -> dict[str, object] | None: ...

    async def timeline(self, incident_id: UUID) -> list[dict[str, object]]: ...

    async def decide(
        self,
        incident_id: UUID,
        recommendation_id: UUID,
        identity: Identity,
        decision: ApprovalDecision,
        rationale: str,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> tuple[Command | None, dict[str, object]]: ...

    async def complete_command(self, command: Command, result: ActionResult) -> ActionResult: ...

    async def command_status(self, command_id: UUID) -> dict[str, object] | None: ...


class ActionAdapter(Protocol):
    identity: str

    async def execute(self, command: Command) -> ActionResult: ...


class TelemetryPublisher(Protocol):
    async def publish(self, event: TelemetryEvent) -> None: ...


class ManagedTelemetryPublisher(TelemetryPublisher, Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...
