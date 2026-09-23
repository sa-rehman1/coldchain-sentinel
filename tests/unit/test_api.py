from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx

from coldchain.api.app import create_app
from coldchain.application.actions import SimulatedColdChainActionAdapter
from coldchain.application.health import ReadinessService
from coldchain.application.interfaces import Identity, ProcessingResult
from coldchain.application.workflow import WorkflowConflictError
from coldchain.config import Settings
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


class HealthyProbe:
    async def ping(self) -> None:
        return None


async def test_liveness_and_generated_correlation_id() -> None:
    app = create_app(Settings(environment="test", database_url=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health/live", headers={"X-Correlation-ID": "invalid"})

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    UUID(response.headers["X-Correlation-ID"])


async def test_valid_correlation_id_is_preserved() -> None:
    correlation_id = "00000000-0000-4000-8000-000000000123"
    app = create_app(Settings(environment="test", database_url=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/health/live", headers={"X-Correlation-ID": correlation_id}
        )

    assert response.headers["X-Correlation-ID"] == correlation_id


async def test_readiness_is_unavailable_without_database_configuration() -> None:
    app = create_app(Settings(environment="test", database_url=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert response.json()["error"]["correlation_id"] == response.headers["X-Correlation-ID"]


async def test_readiness_passes_with_healthy_probe() -> None:
    app = create_app(Settings(environment="test", database_url=None))
    app.state.readiness_service = ReadinessService(HealthyProbe())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ready"}}


async def test_ai_health_is_safe_and_does_not_require_a_key() -> None:
    app = create_app(Settings(environment="test", database_url=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health/ai")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_provider"] == "groq"
    assert payload["live_calls_enabled"] is False
    assert payload["fallback_available"] is True
    assert "api_key" not in str(payload).lower()


async def test_http_errors_use_public_error_envelope() -> None:
    app = create_app(Settings(environment="test", database_url=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"


class FakePublisher:
    def __init__(self) -> None:
        self.event: TelemetryEvent | None = None
        self.events: list[TelemetryEvent] = []

    async def publish(self, event: TelemetryEvent) -> None:
        self.event = event
        self.events.append(event)


class ApiRepository:
    def __init__(self) -> None:
        self.incident_id = uuid4()
        self.recommendation_id = uuid4()
        self.command_id = uuid4()
        self.decisions: dict[str, tuple[tuple[object, ...], UUID]] = {}

    async def demo_run_status(
        self, correlation_id: UUID, event_ids: tuple[UUID, ...]
    ) -> dict[str, object]:
        return {
            "processedEventCount": len(event_ids),
            "dispositions": ["ACCEPTED" for _ in event_ids],
            "incident": None,
        }

    async def recent_readings(
        self, shipment_id: UUID, limit: int
    ) -> tuple[TemperatureReading, ...]:
        return ()

    async def persist_telemetry_result(
        self,
        event: TelemetryEvent,
        evaluation: BreachEvaluation,
        incident: Incident | None,
        evidence: EvidenceSnapshot | None,
        recommendation: Recommendation | None,
        governance: GovernanceEvaluation | None,
    ) -> ProcessingResult:
        return ProcessingResult(False, evaluation.disposition.value, None)

    def _incident(self) -> dict[str, object]:
        now = datetime.now(UTC).isoformat()
        return {
            "incidentId": str(self.incident_id),
            "shipmentId": str(uuid4()),
            "state": "AWAITING_APPROVAL",
            "severity": "CRITICAL",
            "policyVersion": "policy-1",
            "sourceEventIds": [str(uuid4())],
            "correlationId": str(uuid4()),
            "createdAt": now,
            "updatedAt": now,
            "recommendationId": str(self.recommendation_id),
            "recommendedAction": "HOLD_SHIPMENT",
            "recommendationExpiresAt": now,
        }

    async def list_incidents(self) -> list[dict[str, object]]:
        return [self._incident()]

    async def get_incident(self, incident_id: UUID) -> dict[str, object] | None:
        return self._incident() if incident_id == self.incident_id else None

    async def timeline(self, incident_id: UUID) -> list[dict[str, object]]:
        return [
            {
                "sequence": 1,
                "auditEventId": str(uuid4()),
                "eventType": "TELEMETRY_RECEIVED",
                "actorId": "worker",
                "correlationId": str(uuid4()),
                "causationId": None,
                "componentVersion": "1.0",
                "schemaVersion": "1.0",
                "payload": {},
                "occurredAt": datetime.now(UTC).isoformat(),
                "previousEventHash": None,
                "eventHash": "a" * 64,
            }
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
        request = (incident_id, recommendation_id, identity.actor_id, decision, rationale)
        existing = self.decisions.get(idempotency_key)
        if existing is not None and existing[0] != request:
            raise WorkflowConflictError("idempotency key was already used with conflicting input")
        approval_id = existing[1] if existing is not None else uuid4()
        self.decisions[idempotency_key] = (request, approval_id)
        response: dict[str, object] = {
            "approvalId": str(approval_id),
            "decision": decision.value,
            "idempotentReplay": existing is not None,
        }
        if decision is ApprovalDecision.REJECTED:
            return None, response
        return (
            Command(
                self.command_id,
                incident_id,
                recommendation_id,
                approval_id,
                "HOLD_SHIPMENT",
                {},
                idempotency_key,
                datetime.now(UTC),
            ),
            response,
        )

    async def complete_command(self, command: Command, result: ActionResult) -> ActionResult:
        return result

    async def command_status(self, command_id: UUID) -> dict[str, object] | None:
        if command_id != self.command_id:
            return None
        return {
            "commandId": str(command_id),
            "incidentId": str(self.incident_id),
            "actionType": "HOLD_SHIPMENT",
            "status": "SUCCEEDED",
            "adapter": "simulated",
            "detail": "done",
        }


def demo_event() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "eventId": str(uuid4()),
        "correlationId": str(uuid4()),
        "occurredAt": datetime.now(UTC).isoformat(),
        "producer": "api-test",
        "shipmentId": str(uuid4()),
        "vehicleId": "v1",
        "sensorId": "s1",
        "latitude": 1,
        "longitude": 1,
        "temperatureCelsius": 10.5,
        "cargoType": "FRESH_PERISHABLES",
        "readingSequence": 1,
    }


async def test_incident_api_vertical_slice_and_authorization() -> None:
    repository = ApiRepository()
    publisher = FakePublisher()
    app = create_app(
        Settings(environment="test", database_url=None),
        repository,
        publisher,
        SimulatedColdChainActionAdapter(),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        submitted = await client.post("/api/v1/telemetry", json=demo_event())
        listed = await client.get("/api/v1/incidents")
        incident = await client.get(f"/api/v1/incidents/{repository.incident_id}")
        timeline = await client.get(f"/api/v1/incidents/{repository.incident_id}/timeline")
        unauthorized = await client.post(
            f"/api/v1/incidents/{repository.incident_id}/recommendations/"
            f"{repository.recommendation_id}/approve",
            json={"rationale": "verified", "idempotencyKey": "api-approval-unauthorized"},
        )
        approved = await client.post(
            f"/api/v1/incidents/{repository.incident_id}/recommendations/"
            f"{repository.recommendation_id}/approve",
            json={"rationale": "verified", "idempotencyKey": "api-approval-approved"},
            headers={"X-Actor-ID": "dispatcher-1", "X-Actor-Roles": "dispatcher"},
        )
        replay = await client.post(
            f"/api/v1/incidents/{repository.incident_id}/recommendations/"
            f"{repository.recommendation_id}/approve",
            json={"rationale": "verified", "idempotencyKey": "api-approval-approved"},
            headers={"X-Actor-ID": "dispatcher-1", "X-Actor-Roles": "dispatcher"},
        )
        conflict = await client.post(
            f"/api/v1/incidents/{repository.incident_id}/recommendations/"
            f"{repository.recommendation_id}/approve",
            json={"rationale": "changed", "idempotencyKey": "api-approval-approved"},
            headers={"X-Actor-ID": "dispatcher-1", "X-Actor-Roles": "dispatcher"},
        )
        command = await client.get(f"/api/v1/commands/{repository.command_id}")
        missing = await client.get(f"/api/v1/incidents/{uuid4()}")
        missing_timeline = await client.get(f"/api/v1/incidents/{uuid4()}/timeline")
        missing_command = await client.get(f"/api/v1/commands/{uuid4()}")
        rejected = await client.post(
            f"/api/v1/incidents/{repository.incident_id}/recommendations/"
            f"{repository.recommendation_id}/reject",
            json={"rationale": "reject", "idempotencyKey": "api-approval-rejected"},
            headers={"X-Actor-ID": "dispatcher-2", "X-Actor-Roles": "dispatcher"},
        )

    assert submitted.status_code == 202
    assert publisher.event is not None
    assert listed.status_code == incident.status_code == timeline.status_code == 200
    assert unauthorized.status_code == 403
    assert approved.status_code == 200
    assert approved.json()["status"] == "SUCCEEDED"
    assert approved.json()["actionResult"]["status"] == "SUCCEEDED"
    assert replay.status_code == 200
    assert replay.json()["idempotentReplay"] is True
    assert replay.json()["approvalId"] == approved.json()["approvalId"]
    assert conflict.status_code == 409
    assert command.status_code == 200
    assert missing.status_code == 404
    assert missing_timeline.status_code == 404
    assert missing_command.status_code == 404
    assert rejected.json()["decision"] == "REJECTED"


async def test_local_identity_fails_closed_in_production() -> None:
    repository = ApiRepository()
    settings = Settings.model_construct(environment="production", database_url=None)
    app = create_app(settings, repository, FakePublisher())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/incidents/{repository.incident_id}/recommendations/"
            f"{repository.recommendation_id}/reject",
            json={"rationale": "no", "idempotencyKey": "api-production-reject"},
            headers={"X-Actor-ID": "dispatcher-1", "X-Actor-Roles": "dispatcher"},
        )
    assert response.status_code == 403


async def test_workflow_dependencies_fail_closed_when_unconfigured() -> None:
    app = create_app(Settings(environment="test", database_url=None))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        incidents = await client.get("/api/v1/incidents")
        submitted = await client.post("/api/v1/telemetry", json=demo_event())
        approval = await client.post(
            f"/api/v1/incidents/{uuid4()}/recommendations/{uuid4()}/approve",
            json={"rationale": "verified", "idempotencyKey": "api-unconfigured-approval"},
            headers={"X-Actor-ID": "dispatcher-1", "X-Actor-Roles": "dispatcher"},
        )
    assert incidents.status_code == submitted.status_code == approval.status_code == 503


async def test_demo_api_lists_scenarios_and_publishes_only_telemetry() -> None:
    repository = ApiRepository()
    publisher = FakePublisher()
    app = create_app(
        Settings(environment="test", database_url=None, demo_mode_enabled=True),
        repository,
        publisher,
    )
    headers = {"X-Actor-ID": "dispatcher:demo", "X-Actor-Roles": "dispatcher"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        scenarios = await client.get("/api/v1/demo/scenarios", headers=headers)
        first = await client.post("/api/v1/demo/scenarios/sustained", headers=headers)
        second = await client.post("/api/v1/demo/scenarios/sustained", headers=headers)
        duplicate = await client.post("/api/v1/demo/scenarios/duplicate", headers=headers)
        run = await client.get(f"/api/v1/demo/runs/{first.json()['runId']}", headers=headers)

    assert scenarios.status_code == 200
    assert {item["scenarioId"] for item in scenarios.json()} >= {
        "healthy",
        "critical",
        "sustained",
        "stale",
        "duplicate",
        "fallback",
    }
    assert first.status_code == second.status_code == duplicate.status_code == 202
    assert first.json()["eventIds"] != second.json()["eventIds"]
    assert first.json()["correlationId"] != second.json()["correlationId"]
    assert duplicate.json()["publishCount"] == 2
    assert len(set(duplicate.json()["eventIds"])) == 1
    assert run.status_code == 200
    assert run.json()["status"] == "COMPLETED_WITHOUT_INCIDENT"
    assert all(event.producer.startswith("coldchain-local-demo:") for event in publisher.events)


async def test_demo_api_is_disabled_and_role_enforced() -> None:
    repository = ApiRepository()
    publisher = FakePublisher()
    disabled = create_app(Settings(environment="test", database_url=None), repository, publisher)
    enabled = create_app(
        Settings(environment="test", database_url=None, demo_mode_enabled=True),
        repository,
        publisher,
    )
    auditor = {"X-Actor-ID": "auditor:demo", "X-Actor-Roles": "auditor"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=disabled), base_url="http://test"
    ) as client:
        hidden = await client.get("/api/v1/demo/scenarios", headers=auditor)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=enabled), base_url="http://test"
    ) as client:
        forbidden = await client.post("/api/v1/demo/scenarios/healthy", headers=auditor)

    assert hidden.status_code == 404
    assert forbidden.status_code == 403
    assert publisher.events == []
