"""Stable metadata for the isolated local portfolio showcase dataset."""

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5


def showcase_uuid(kind: str, slug: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"coldchain-sentinel-showcase:{kind}:{slug}")


@dataclass(frozen=True, slots=True)
class ShowcaseEvidenceProfile:
    sensor_health: str
    calibration: str
    sample_interval_minutes: int
    reading_quality: str
    product_sensitivity: str
    custody_verification: str


CANONICAL_EVIDENCE_PROFILE = ShowcaseEvidenceProfile(
    sensor_health="Healthy",
    calibration="Verified",
    sample_interval_minutes=10,
    reading_quality="No quality flags",
    product_sensitivity="High",
    custody_verification="Complete",
)


SHOWCASE_SOP_SECTIONS_BY_ACTION: dict[str, tuple[tuple[str, str, str], ...]] = {
    "HOLD_SHIPMENT": (
        (
            "CCS-SOP-TEMP-001",
            "TEMP-001-S2",
            "The complete temperature-excursion evidence supports a shipment hold "
            "pending dispatcher review.",
        ),
        (
            "CCS-SOP-HOLD-001",
            "HOLD-001-S1",
            "The proposed hold requires authenticated human approval and cannot be "
            "executed by the recommendation provider.",
        ),
    ),
    "REQUEST_INSPECTION": (
        (
            "CCS-SOP-HOLD-001",
            "HOLD-001-S2",
            "The excursion requires the documented independent inspection checks in this section.",
        ),
        (
            "CCS-SOP-EVID-001",
            "EVID-001-S2",
            "The incident evidence includes the sensor-integrity checks required "
            "before disposition.",
        ),
    ),
    "CONTINUE_MONITORING": (
        (
            "CCS-SOP-TEMP-001",
            "TEMP-001-S1",
            "The resolved excursion remains governed by deterministic policy and "
            "ordered telemetry.",
        ),
        (
            "CCS-SOP-EVID-001",
            "EVID-001-S2",
            "Continued monitoring relies on the verified sensor-integrity evidence described here.",
        ),
    ),
}


@dataclass(frozen=True, slots=True)
class ShowcaseShipment:
    slug: str
    reference: str
    incident_reference: str | None
    route_from: str
    route_via: str
    route_to: str
    route_progress: int
    product_label: str
    sensor_label: str
    cargo_type: str
    permitted_min: float
    permitted_max: float
    temperatures: tuple[float, ...]
    incident_state: str | None = None
    incident_severity: str | None = None
    incident_age_minutes: int | None = None
    recommendation_action: str | None = None
    recommendation_expiry_minutes: int | None = None
    evidence_profile: ShowcaseEvidenceProfile | None = None

    @property
    def shipment_id(self) -> UUID:
        return showcase_uuid("shipment", self.slug)

    @property
    def incident_id(self) -> UUID | None:
        return showcase_uuid("incident", self.slug) if self.incident_state else None


SHOWCASE_SHIPMENTS: tuple[ShowcaseShipment, ...] = (
    ShowcaseShipment(
        "vaccines-austin-dallas",
        "CCS-1001",
        "INC-1001",
        "Austin",
        "Waco",
        "Dallas",
        68,
        "mRNA vaccines",
        "Probe 01",
        "VACCINES",
        2.0,
        8.0,
        (4.2, 4.8, 6.1, 9.7, 12.4),
        "AWAITING_APPROVAL",
        "CRITICAL",
        18,
        "HOLD_SHIPMENT",
        12,
        CANONICAL_EVIDENCE_PROFILE,
    ),
    ShowcaseShipment(
        "salmon-seattle-portland",
        "CCS-1002",
        "INC-1002",
        "Seattle",
        "Tacoma",
        "Portland",
        54,
        "Fresh salmon",
        "Probe 02",
        "FRESH_SEAFOOD",
        -1.0,
        4.0,
        (1.8, 2.1, 3.7, 6.4, 9.8),
        "AWAITING_APPROVAL",
        "CRITICAL",
        34,
        "HOLD_SHIPMENT",
        46,
        CANONICAL_EVIDENCE_PROFILE,
    ),
    ShowcaseShipment(
        "berries-fresno-los-angeles",
        "CCS-1003",
        "INC-1003",
        "Fresno",
        "Bakersfield",
        "Los Angeles",
        73,
        "Fresh berries",
        "Probe 03",
        "FRESH_PRODUCE",
        0.0,
        5.0,
        (3.2, 3.8, 4.6, 5.8, 7.1),
        "EVIDENCE_COLLECTED",
        "HIGH",
        27,
        "REQUEST_INSPECTION",
        55,
        CANONICAL_EVIDENCE_PROFILE,
    ),
    ShowcaseShipment(
        "cultures-madison-chicago",
        "CCS-1004",
        "INC-1004",
        "Madison",
        "Rockford",
        "Chicago",
        100,
        "Dairy cultures",
        "Probe 04",
        "DAIRY_CULTURES",
        2.0,
        6.0,
        (4.1, 4.5, 6.3, 7.4, 5.2),
        "RESOLVED",
        "HIGH",
        49,
        "CONTINUE_MONITORING",
        60,
        CANONICAL_EVIDENCE_PROFILE,
    ),
    ShowcaseShipment(
        "biologics-boston-new-york",
        "CCS-1005",
        None,
        "Boston",
        "Hartford",
        "New York",
        41,
        "Clinical biologics",
        "Probe 05",
        "BIOLOGICS",
        2.0,
        8.0,
        (4.4, 4.2, 4.6, 4.5, 4.3),
    ),
    ShowcaseShipment(
        "insulin-phoenix-tucson",
        "CCS-1006",
        None,
        "Phoenix",
        "Casa Grande",
        "Tucson",
        82,
        "Insulin",
        "Probe 06",
        "INSULIN",
        2.0,
        8.0,
        (5.1, 5.0, 5.2, 5.1, 5.0),
    ),
    ShowcaseShipment(
        "produce-sacramento-reno",
        "CCS-1007",
        None,
        "Sacramento",
        "Truckee",
        "Reno",
        36,
        "Leafy greens",
        "Probe 07",
        "FRESH_PRODUCE",
        0.0,
        5.0,
        (3.5, 3.6, 3.4, 3.7, 3.5),
    ),
)

SHOWCASE_BY_SHIPMENT_ID = {item.shipment_id: item for item in SHOWCASE_SHIPMENTS}
