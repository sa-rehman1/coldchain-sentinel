"""Typed, server-owned metadata for local Demo Lab telemetry."""

from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from coldchain.contracts.models import TelemetryEvent

DEMO_PRODUCER_PREFIX = "coldchain-local-demo:"


def demo_incident_reference(incident_id: UUID) -> str:
    public_id = uuid5(NAMESPACE_URL, f"coldchain-demo-incident:{incident_id}")
    return f"INC-DEMO-{public_id.hex[:8].upper()}"


def demo_shipment_reference(shipment_id: UUID) -> str:
    public_id = uuid5(NAMESPACE_URL, f"coldchain-demo-shipment:{shipment_id}")
    return f"CCS-DEMO-{public_id.hex[:8].upper()}"


def demo_evidence_reference(evidence_id: UUID) -> str:
    public_id = uuid5(NAMESPACE_URL, f"coldchain-demo-evidence:{evidence_id}")
    return f"EVD-DEMO-{public_id.hex[:8].upper()}"


@dataclass(frozen=True, slots=True)
class DemoShipmentProjection:
    """Safe labels and evidence facts carried with synthetic telemetry."""

    scenario_id: str
    shipment_reference: str
    sensor_label: str
    product_label: str
    route_origin: str
    route_via: str
    route_destination: str
    route_progress: int
    sensor_health: str
    calibration: str
    sample_interval_minutes: int
    reading_quality: str
    product_sensitivity: str
    custody_verification: str

    @classmethod
    def for_event(cls, event: TelemetryEvent) -> "DemoShipmentProjection | None":
        if not event.producer.startswith(DEMO_PRODUCER_PREFIX):
            return None
        scenario_id = event.producer.removeprefix(DEMO_PRODUCER_PREFIX)
        return cls(
            scenario_id=scenario_id,
            shipment_reference=demo_shipment_reference(event.shipment_id),
            sensor_label="Probe DEMO-01",
            product_label="Synthetic fresh perishables",
            route_origin="Chicago, IL",
            route_via="Des Moines, IA",
            route_destination="Denver, CO",
            route_progress=55,
            sensor_health="Healthy",
            calibration="Verified",
            sample_interval_minutes=1,
            reading_quality="No quality flags",
            product_sensitivity="High",
            custody_verification="Complete",
        )

    @classmethod
    def from_policy_inputs(cls, inputs: dict[str, Any]) -> "DemoShipmentProjection | None":
        value = inputs.get("demoProjection")
        if not isinstance(value, dict):
            return None
        try:
            return cls(
                scenario_id=str(value["scenarioId"]),
                shipment_reference=str(value["shipmentReference"]),
                sensor_label=str(value["sensorLabel"]),
                product_label=str(value["productLabel"]),
                route_origin=str(value["routeOrigin"]),
                route_via=str(value["routeVia"]),
                route_destination=str(value["routeDestination"]),
                route_progress=int(value["routeProgress"]),
                sensor_health=str(value["sensorHealth"]),
                calibration=str(value["calibration"]),
                sample_interval_minutes=int(value["sampleIntervalMinutes"]),
                reading_quality=str(value["readingQuality"]),
                product_sensitivity=str(value["productSensitivity"]),
                custody_verification=str(value["custodyVerification"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def as_policy_input(self) -> dict[str, str | int]:
        return {
            "scenarioId": self.scenario_id,
            "shipmentReference": self.shipment_reference,
            "sensorLabel": self.sensor_label,
            "productLabel": self.product_label,
            "routeOrigin": self.route_origin,
            "routeVia": self.route_via,
            "routeDestination": self.route_destination,
            "routeProgress": self.route_progress,
            "sensorHealth": self.sensor_health,
            "calibration": self.calibration,
            "sampleIntervalMinutes": self.sample_interval_minutes,
            "readingQuality": self.reading_quality,
            "productSensitivity": self.product_sensitivity,
            "custodyVerification": self.custody_verification,
        }
