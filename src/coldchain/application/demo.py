"""Local-only demo scenarios that enter the normal Kafka workflow."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

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
            "steps": {
                "telemetrySubmitted": True,
                "eventAccepted": True,
                "policyEvaluated": processed > 0,
                "evidenceCollected": bool(incident and incident.get("evidence")),
                "recommendationCreated": bool(incident and incident.get("recommendation")),
                "governanceCompleted": bool(incident and incident.get("governance")),
                "incidentReady": incident is not None,
            },
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
