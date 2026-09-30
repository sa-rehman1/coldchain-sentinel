"""Local-only demo scenarios that enter the normal Kafka workflow."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, cast
from uuid import UUID, uuid4

from coldchain.application.demo_projection import demo_incident_reference
from coldchain.application.interfaces import TelemetryPublisher
from coldchain.contracts.models import TelemetryEvent


@dataclass(frozen=True, slots=True)
class DemoScenario:
    scenario_id: str
    title: str
    description: str
    expected_outcome: str
    human_action: str


SCENARIOS: tuple[DemoScenario, ...] = (
    DemoScenario("healthy", "Healthy shipment", "Valid in-range telemetry", "No incident", "None"),
    DemoScenario(
        "critical",
        "Immediate critical breach",
        "One clearly unsafe temperature reading",
        "Critical incident",
        "Review required",
    ),
    DemoScenario(
        "sustained",
        "Sustained temperature breach",
        "Three consecutive readings above the safe limit",
        "Approval required",
        "Approve or reject hold",
    ),
    DemoScenario(
        "stale",
        "Stale telemetry",
        "A valid reading older than the policy freshness window",
        "Stale evidence recorded",
        "Request fresh reading",
    ),
    DemoScenario(
        "duplicate",
        "Duplicate delivery",
        "The same valid event is published twice",
        "One durable processing result",
        "None",
    ),
    DemoScenario(
        "fallback",
        "Provider-disabled fallback",
        "A sustained breach while external AI calls are disabled",
        "Deterministic fallback and approval required",
        "Approve or reject hold",
    ),
)


class DemoRunReader(Protocol):
    async def demo_run_status(
        self, correlation_id: UUID, event_ids: tuple[UUID, ...]
    ) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class DemoRun:
    run_id: UUID
    scenario_id: str
    correlation_id: UUID
    shipment_id: UUID
    event_ids: tuple[UUID, ...]
    publish_count: int
    started_at: datetime


DemoStageState = Literal["PENDING", "COMPLETED", "NOT_REQUIRED", "BLOCKED", "FAILED"]
DemoResultState = Literal["PROCESSING", "COMPLETE", "AWAITING_HUMAN_REVIEW", "BLOCKED", "FAILED"]


class DemoScenarioService:
    """Publish synthetic telemetry and read its durable workflow status."""

    def __init__(self, publisher: TelemetryPublisher, reader: DemoRunReader) -> None:
        self._publisher = publisher
        self._reader = reader
        self._runs: dict[UUID, DemoRun] = {}

    @staticmethod
    def scenarios() -> tuple[DemoScenario, ...]:
        return SCENARIOS

    async def start(self, scenario_id: str) -> DemoRun:
        if scenario_id not in {item.scenario_id for item in SCENARIOS}:
            raise KeyError(scenario_id)
        now = datetime.now(UTC)
        run_id = uuid4()
        correlation_id = uuid4()
        shipment_id = uuid4()
        events = self._events(scenario_id, now, correlation_id, shipment_id)
        publish_events = (*events, events[-1]) if scenario_id == "duplicate" else events
        for event in publish_events:
            await self._publisher.publish(event)
        run = DemoRun(
            run_id=run_id,
            scenario_id=scenario_id,
            correlation_id=correlation_id,
            shipment_id=shipment_id,
            event_ids=tuple(event.event_id for event in events),
            publish_count=len(publish_events),
            started_at=now,
        )
        self._runs[run_id] = run
        return run

    async def status(self, run_id: UUID) -> dict[str, object] | None:
        run = self._runs.get(run_id)
        if run is None:
            return None
        durable = await self._reader.demo_run_status(run.correlation_id, run.event_ids)
        processed = cast(int, durable["processedEventCount"])
        incident_value = durable.get("incident")
        incident = cast(dict[str, Any] | None, incident_value)
        complete = processed == len(run.event_ids)
        governance_value = incident.get("governance") if incident else None
        governance = cast(dict[str, Any] | None, governance_value)
        governance_decision = (
            str(governance["decision"])
            if governance is not None and governance.get("decision") is not None
            else None
        )
        human_decision_recorded = bool(incident and incident.get("approval"))
        incident_id = UUID(str(incident["incidentId"])) if incident else None
        incident_reference = (
            str(incident.get("incidentReference"))
            if incident and incident.get("incidentReference")
            else demo_incident_reference(incident_id)
            if incident_id is not None
            else None
        )
        shipment_reference = (
            str(incident.get("shipmentReference"))
            if incident and incident.get("shipmentReference")
            else None
        )
        incident_severity = (
            str(incident.get("severity")) if incident and incident.get("severity") else None
        )
        result_state = self._result_state(
            complete=complete,
            incident=incident,
            governance_decision=governance_decision,
            human_decision_recorded=human_decision_recorded,
        )
        stage_states = self._stage_states(
            processed=processed,
            complete=complete,
            incident=incident,
            governance_decision=governance_decision,
            human_decision_recorded=human_decision_recorded,
        )
        return {
            "runId": str(run.run_id),
            "scenarioId": run.scenario_id,
            "correlationId": str(run.correlation_id),
            "shipmentId": str(run.shipment_id),
            "eventIds": [str(item) for item in run.event_ids],
            "publishCount": run.publish_count,
            "startedAt": run.started_at.isoformat(),
            "status": (
                "INCIDENT_READY"
                if incident is not None
                else "COMPLETED_WITHOUT_INCIDENT"
                if complete
                else "PROCESSING"
            ),
            "processedEventCount": processed,
            "dispositions": durable["dispositions"],
            "incident": incident,
            "incidentId": str(incident_id) if incident_id is not None else None,
            "incidentReference": incident_reference,
            "shipmentReference": shipment_reference,
            "incidentSeverity": incident_severity,
            "governanceDecision": governance_decision,
            "humanDecisionRecorded": human_decision_recorded,
            "resultState": result_state,
            "steps": stage_states,
        }

    @staticmethod
    def _result_state(
        *,
        complete: bool,
        incident: dict[str, Any] | None,
        governance_decision: str | None,
        human_decision_recorded: bool,
    ) -> DemoResultState:
        if incident is None:
            return "COMPLETE" if complete else "PROCESSING"
        if governance_decision in {"PROHIBITED", "KILL_SWITCH_ACTIVE"}:
            return "BLOCKED"
        if governance_decision == "APPROVAL_REQUIRED" and not human_decision_recorded:
            return "AWAITING_HUMAN_REVIEW"
        if governance_decision is None:
            return "PROCESSING"
        return "COMPLETE"

    @staticmethod
    def _stage_states(
        *,
        processed: int,
        complete: bool,
        incident: dict[str, Any] | None,
        governance_decision: str | None,
        human_decision_recorded: bool,
    ) -> dict[str, DemoStageState]:
        processed_state: DemoStageState = "COMPLETED" if processed > 0 else "PENDING"
        if incident is None:
            downstream: DemoStageState = "NOT_REQUIRED" if complete else "PENDING"
            return {
                "sensorReading": processed_state,
                "policyCheck": processed_state,
                "incidentCreated": downstream,
                "evidenceCollected": downstream,
                "aiAdvisory": downstream,
                "governance": downstream,
                "humanReview": downstream,
            }

        governance_complete = governance_decision is not None
        if human_decision_recorded:
            human_review: DemoStageState = "COMPLETED"
        elif governance_decision == "APPROVAL_REQUIRED":
            human_review = "PENDING"
        elif governance_decision in {"PROHIBITED", "KILL_SWITCH_ACTIVE"}:
            human_review = "NOT_REQUIRED"
        else:
            human_review = "PENDING"
        return {
            "sensorReading": processed_state,
            "policyCheck": processed_state,
            "incidentCreated": "COMPLETED",
            "evidenceCollected": "COMPLETED" if incident.get("evidence") else "PENDING",
            "aiAdvisory": "COMPLETED" if incident.get("recommendation") else "PENDING",
            "governance": "COMPLETED" if governance_complete else "PENDING",
            "humanReview": human_review,
        }

    @staticmethod
    def _events(
        scenario_id: str,
        now: datetime,
        correlation_id: UUID,
        shipment_id: UUID,
    ) -> tuple[TelemetryEvent, ...]:
        values: tuple[tuple[float, timedelta], ...]
        if scenario_id in {"sustained", "fallback"}:
            values = ((8.7, timedelta(minutes=2)), (9.1, timedelta(minutes=1)), (9.4, timedelta()))
        elif scenario_id == "critical":
            values = ((12.4, timedelta()),)
        elif scenario_id == "stale":
            values = ((9.2, timedelta(minutes=20)),)
        elif scenario_id == "duplicate":
            values = ((5.1, timedelta()),)
        else:
            values = ((5.4, timedelta()),)
        return tuple(
            TelemetryEvent(
                event_id=uuid4(),
                correlation_id=correlation_id,
                occurred_at=now - age,
                producer=f"coldchain-local-demo:{scenario_id}",
                shipment_id=shipment_id,
                vehicle_id="CCS-DEMO-VEHICLE",
                sensor_id="CCS-DEMO-SENSOR",
                latitude=41.8781,
                longitude=-87.6298,
                temperature_celsius=temperature,
                cargo_type="FRESH_PERISHABLES",
                reading_sequence=index,
            )
            for index, (temperature, age) in enumerate(values, start=1)
        )
