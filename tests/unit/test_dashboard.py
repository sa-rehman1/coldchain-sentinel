from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from coldchain.application.dashboard import (
    DashboardIncidentFact,
    aggregate_incident_activity,
    summarize_incidents,
)
from coldchain.application.showcase import SHOWCASE_SHIPMENTS
from coldchain.infrastructure.database import Database
from coldchain.infrastructure.models import (
    AuditEventRecord,
    EvidenceRecord,
    GovernanceRecord,
    IncidentRecord,
    PlatformMetadata,
    RecommendationRecord,
    TelemetryRecord,
)
from coldchain.infrastructure.showcase import prepare_showcase


def _fact(
    *,
    shipment_id: UUID | None = None,
    state: str,
    severity: str,
    created_at: datetime,
    updated_at: datetime | None = None,
    decided: bool = False,
) -> DashboardIncidentFact:
    return DashboardIncidentFact(
        shipment_id=shipment_id or uuid4(),
        state=state,
        severity=severity,
        created_at=created_at,
        updated_at=updated_at or created_at,
        has_human_decision=decided,
    )


def test_dashboard_metrics_reconcile_distinct_shipments_and_pending_reviews() -> None:
    now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    repeated_shipment = uuid4()
    facts = (
        _fact(
            shipment_id=repeated_shipment,
            state="AWAITING_APPROVAL",
            severity="CRITICAL",
            created_at=now - timedelta(minutes=20),
        ),
        _fact(
            shipment_id=repeated_shipment,
            state="RESOLVED",
            severity="HIGH",
            created_at=now - timedelta(minutes=50),
            updated_at=now - timedelta(minutes=5),
            decided=True,
        ),
        _fact(
            state="EVIDENCE_COLLECTED",
            severity="HIGH",
            created_at=now - timedelta(minutes=8),
        ),
    )

    summary = summarize_incidents(facts)

    assert summary.affected_shipments == 2
    assert summary.open_incidents == 2
    assert summary.awaiting_human_review == 1
    assert summary.critical_incidents + summary.warning_incidents + summary.normal_incidents == 3


def test_activity_is_aggregated_into_bounded_time_buckets() -> None:
    now = datetime(2026, 9, 24, 12, 3, tzinfo=UTC)
    facts = (
        _fact(
            state="AWAITING_APPROVAL",
            severity="CRITICAL",
            created_at=now - timedelta(minutes=12),
        ),
        _fact(
            state="RESOLVED",
            severity="HIGH",
            created_at=now - timedelta(minutes=42),
            updated_at=now - timedelta(minutes=3),
            decided=True,
        ),
    )

    buckets = aggregate_incident_activity(facts, now)

    assert len(buckets) == 6
    assert sum(bucket["critical"] for bucket in buckets) == 1
    assert sum(bucket["warning"] for bucket in buckets) == 1
    assert sum(bucket["resolved"] for bucket in buckets) == 1


class _SeedSession:
    def __init__(self) -> None:
        self.merged: list[object] = []
        self.scalar_results = iter((*([None] * 40), 35, 4))
        self.added: list[object] = []
        self.flush_count = 0

    async def merge(self, record: object) -> object:
        self.merged.append(record)
        return record

    async def scalar(self, _statement: object) -> int | None:
        return next(self.scalar_results)

    def add(self, record: object) -> None:
        self.added.append(record)

    async def flush(self) -> None:
        self.flush_count += 1


class _SeedDatabase:
    def __init__(self) -> None:
        self.session = _SeedSession()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[_SeedSession]:
        yield self.session


async def test_showcase_seed_builds_only_bounded_deterministic_records() -> None:
    database = _SeedDatabase()
    result = await prepare_showcase(
        cast(Database, cast(Any, database)),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )

    assert result.shipments == 7
    assert result.telemetry_records == 35
    assert result.incidents == 4
    assert result.pending_reviews == 2
    assert len(database.session.merged) == 1 + 35 + (4 * 4)
    assert sum(isinstance(item, PlatformMetadata) for item in database.session.merged) == 1
    assert sum(isinstance(item, TelemetryRecord) for item in database.session.merged) == 35
    assert sum(isinstance(item, IncidentRecord) for item in database.session.merged) == 4
    assert sum(isinstance(item, EvidenceRecord) for item in database.session.merged) == 4
    assert sum(isinstance(item, RecommendationRecord) for item in database.session.merged) == 4
    assert sum(isinstance(item, GovernanceRecord) for item in database.session.merged) == 4
    assert database.session.flush_count == 32
    assert sum(isinstance(item, AuditEventRecord) for item in database.session.added) == 20
    assert all(
        item.provider == "deterministic" and item.non_authoritative
        for item in database.session.merged
        if isinstance(item, RecommendationRecord)
    )
    assert {shipment.reference for shipment in SHOWCASE_SHIPMENTS} == {
        f"CCS-{number}" for number in range(1001, 1008)
    }
