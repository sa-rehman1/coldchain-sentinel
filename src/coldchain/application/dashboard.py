"""Pure dashboard metric definitions for the local control-tower read model."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID

TERMINAL_INCIDENT_STATES = frozenset({"REJECTED", "RESOLVED"})


@dataclass(frozen=True, slots=True)
class DashboardIncidentFact:
    """Small, persistence-independent incident projection used by dashboard metrics."""

    shipment_id: UUID
    state: str
    severity: str
    created_at: datetime
    updated_at: datetime
    has_human_decision: bool


@dataclass(frozen=True, slots=True)
class DashboardMetricSummary:
    affected_shipments: int
    open_incidents: int
    awaiting_human_review: int
    critical_incidents: int
    warning_incidents: int
    normal_incidents: int


class IncidentActivityBucket(TypedDict):
    label: str
    startsAt: str
    critical: int
    warning: int
    resolved: int


def summarize_incidents(facts: tuple[DashboardIncidentFact, ...]) -> DashboardMetricSummary:
    """Calculate reconciled headline counts from one immutable incident set.

    Affected shipments are distinct shipments represented by any scoped incident. Open
    incidents exclude the two terminal workflow states. Awaiting review requires both the
    awaiting-approval state and the absence of a recorded human decision. Severity totals
    classify every incident in the same scoped set exactly once.
    """

    return DashboardMetricSummary(
        affected_shipments=len({fact.shipment_id for fact in facts}),
        open_incidents=sum(fact.state not in TERMINAL_INCIDENT_STATES for fact in facts),
        awaiting_human_review=sum(
            fact.state == "AWAITING_APPROVAL" and not fact.has_human_decision for fact in facts
        ),
        critical_incidents=sum(fact.severity == "CRITICAL" for fact in facts),
        warning_incidents=sum(fact.severity in {"HIGH", "MEDIUM"} for fact in facts),
        normal_incidents=sum(fact.severity not in {"CRITICAL", "HIGH", "MEDIUM"} for fact in facts),
    )


def aggregate_incident_activity(
    facts: tuple[DashboardIncidentFact, ...],
    now: datetime,
    *,
    bucket_minutes: int = 10,
    bucket_count: int = 6,
) -> list[IncidentActivityBucket]:
    """Aggregate incident creation and resolution into bounded recent time buckets."""

    current = now.astimezone(UTC)
    bucket_end = current.replace(
        minute=(current.minute // bucket_minutes) * bucket_minutes,
        second=0,
        microsecond=0,
    ) + timedelta(minutes=bucket_minutes)
    bucket_start = bucket_end - timedelta(minutes=bucket_minutes * bucket_count)
    buckets: list[IncidentActivityBucket] = []
    for index in range(bucket_count):
        start = bucket_start + timedelta(minutes=index * bucket_minutes)
        end = start + timedelta(minutes=bucket_minutes)
        created = tuple(fact for fact in facts if start <= fact.created_at.astimezone(UTC) < end)
        resolved = sum(
            fact.state in TERMINAL_INCIDENT_STATES
            and start <= fact.updated_at.astimezone(UTC) < end
            for fact in facts
        )
        buckets.append(
            {
                "label": start.strftime("%H:%M"),
                "startsAt": start.isoformat(),
                "critical": sum(fact.severity == "CRITICAL" for fact in created),
                "warning": sum(fact.severity in {"HIGH", "MEDIUM"} for fact in created),
                "resolved": resolved,
            }
        )
    return buckets
