import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest


@pytest.mark.e2e
async def test_docker_temperature_breach_workflow() -> None:
    base_url = os.getenv("COLDCHAIN_E2E_BASE_URL")
    if not base_url:
        pytest.skip("COLDCHAIN_E2E_BASE_URL is not configured")
    shipment_id = uuid4()
    event = {
        "schemaVersion": "1.0",
        "eventId": str(uuid4()),
        "correlationId": str(uuid4()),
        "occurredAt": datetime.now(UTC).isoformat(),
        "producer": "docker-e2e-test",
        "shipmentId": str(shipment_id),
        "vehicleId": "e2e-vehicle",
        "sensorId": "e2e-sensor",
        "latitude": 33.77,
        "longitude": -118.19,
        "temperatureCelsius": 10.5,
        "cargoType": "FRESH_PERISHABLES",
        "readingSequence": 1,
    }
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        accepted = await client.post("/telemetry", json=event)
        assert accepted.status_code == 202
        incident = None
        for _ in range(20):
            incidents = (await client.get("/incidents")).json()
            incident = next(
                (item for item in incidents if item["shipmentId"] == str(shipment_id)), None
            )
            if incident is not None:
                break
            await asyncio.sleep(0.5)
        assert incident is not None
        detail = (await client.get(f"/incidents/{incident['incidentId']}")).json()
        approval = await client.post(
            (
                f"/incidents/{detail['incidentId']}/recommendations/"
                f"{detail['recommendationId']}/approve"
            ),
            json={
                "rationale": "Docker E2E evidence reviewed",
                "idempotencyKey": f"docker-e2e-{shipment_id}",
            },
            headers={"X-Actor-ID": "dispatcher:e2e", "X-Actor-Roles": "dispatcher"},
        )
        assert approval.status_code == 200
        assert approval.json()["status"] == "SUCCEEDED"
        replay = await client.post(
            (
                f"/incidents/{detail['incidentId']}/recommendations/"
                f"{detail['recommendationId']}/approve"
            ),
            json={
                "rationale": "Docker E2E evidence reviewed",
                "idempotencyKey": f"docker-e2e-{shipment_id}",
            },
            headers={"X-Actor-ID": "dispatcher:e2e", "X-Actor-Roles": "dispatcher"},
        )
        assert replay.status_code == 200
        assert replay.json()["idempotentReplay"] is True
        assert replay.json()["approvalId"] == approval.json()["approvalId"]
        assert replay.json()["commandId"] == approval.json()["commandId"]
        assert replay.json()["actionResult"] == approval.json()["actionResult"]
        conflict = await client.post(
            (
                f"/incidents/{detail['incidentId']}/recommendations/"
                f"{detail['recommendationId']}/approve"
            ),
            json={
                "rationale": "Conflicting E2E rationale",
                "idempotencyKey": f"docker-e2e-{shipment_id}",
            },
            headers={"X-Actor-ID": "dispatcher:e2e", "X-Actor-Roles": "dispatcher"},
        )
        assert conflict.status_code == 409
        command = await client.get(f"/commands/{approval.json()['commandId']}")
        assert command.json()["status"] == "SUCCEEDED"
        timeline = (await client.get(f"/incidents/{detail['incidentId']}/timeline")).json()
        assert [item["eventType"] for item in timeline] == [
            "TELEMETRY_RECEIVED",
            "BREACH_POLICY_EVALUATED",
            "EVIDENCE_SNAPSHOT_CREATED",
            "RECOMMENDATION_CREATED",
            "GOVERNANCE_EVALUATED",
            "HUMAN_DECISION_RECORDED",
            "COMMAND_CREATED",
            "SIMULATED_ACTION_COMPLETED",
        ]
