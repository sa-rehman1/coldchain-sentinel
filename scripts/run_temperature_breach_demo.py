"""Run the deterministic temperature-breach scenario against a local API."""

import argparse
import json
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

SHIPMENT_ID = "10000000-0000-4000-8000-000000000001"
EVENT_ID = "10000000-0000-4000-8000-000000000002"
CORRELATION_ID = "10000000-0000-4000-8000-000000000003"


def request_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost",
        "127.0.0.1",
    }:
        raise ValueError("demo requests are restricted to the local API")
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    args = parser.parse_args()
    event = {
        "schemaVersion": "1.0",
        "eventId": EVENT_ID,
        "correlationId": CORRELATION_ID,
        "occurredAt": datetime.now(UTC).isoformat(),
        "producer": "coldchain-local-demo",
        "shipmentId": SHIPMENT_ID,
        "vehicleId": "demo-vehicle-1",
        "sensorId": "demo-sensor-1",
        "latitude": 33.77,
        "longitude": -118.19,
        "temperatureCelsius": 10.5,
        "cargoType": "FRESH_PERISHABLES",
        "readingSequence": 1,
    }
    request_json("POST", f"{args.base_url}/telemetry", event)
    incident: dict[str, Any] | None = None
    for _ in range(20):
        incidents = request_json("GET", f"{args.base_url}/incidents")
        incident = next((item for item in incidents if item["shipmentId"] == SHIPMENT_ID), None)
        if incident is not None:
            break
        time.sleep(0.5)
    if incident is None:
        raise SystemExit("incident was not created within 10 seconds")
    incident = request_json("GET", f"{args.base_url}/incidents/{incident['incidentId']}")
    decision = request_json(
        "POST",
        (
            f"{args.base_url}/incidents/{incident['incidentId']}/recommendations/"
            f"{incident['recommendationId']}/approve"
        ),
        {
            "rationale": "Deterministic demo evidence reviewed",
            "idempotencyKey": "coldchain-local-demo-approval-v1",
        },
        {"X-Actor-ID": "dispatcher:demo", "X-Actor-Roles": "dispatcher"},
    )
    timeline = request_json("GET", f"{args.base_url}/incidents/{incident['incidentId']}/timeline")
    print(
        json.dumps(
            {
                "incidentId": incident["incidentId"],
                "commandId": decision["commandId"],
                "commandStatus": decision["status"],
                "timelineEventTypes": [item["eventType"] for item in timeline],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
