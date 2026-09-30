"""Idempotent, narrowly scoped preparation for the local portfolio showcase."""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from coldchain.application.showcase import (
    SHOWCASE_SHIPMENTS,
    SHOWCASE_SOP_SECTIONS_BY_ACTION,
    showcase_uuid,
)
from coldchain.config import get_settings
from coldchain.infrastructure.database import Database, build_database
from coldchain.infrastructure.models import (
    EvidenceRecord,
    GovernanceRecord,
    IncidentRecord,
    PlatformMetadata,
    RecommendationRecord,
    TelemetryRecord,
)
from coldchain.infrastructure.repositories import append_audit_event
from coldchain.retrieval.core import SopChunk, chunk_document
from coldchain.retrieval.corpus import CORPUS_VERSION, load_corpus


@dataclass(frozen=True, slots=True)
class ShowcaseSeedResult:
    shipments: int
    telemetry_records: int
    incidents: int
    pending_reviews: int


def _showcase_citations(action: str, *, as_of: datetime) -> tuple[tuple[SopChunk, str, str], ...]:
    requested = SHOWCASE_SOP_SECTIONS_BY_ACTION[action]
    documents = load_corpus()
    titles = {document.document_id: document.title for document in documents}
    by_section = {
        (chunk.document_id, chunk.section_id): chunk
        for document in documents
        for chunk in chunk_document(document)
    }
    citations: list[tuple[SopChunk, str, str]] = []
    for document_id, section_id, why_applicable in requested:
        chunk = by_section[(document_id, section_id)]
        if chunk.effective_date > as_of.date():
            continue
        if chunk.superseded_date is not None and chunk.superseded_date <= as_of.date():
            continue
        citations.append((chunk, titles[document_id], why_applicable))
    if len(citations) != len(requested):
        raise RuntimeError(f"showcase SOP selection is not effective for {action}")
    return tuple(citations)


async def prepare_showcase(
    database: Database, *, now: datetime | None = None
) -> ShowcaseSeedResult:
    """Upsert only stable showcase-owned rows and leave every unrelated row untouched."""

    generated_at = (now or datetime.now(UTC)).astimezone(UTC)
    telemetry_count = 0
    incident_count = 0
    pending_count = 0
    async with database.transaction() as session:
        await session.merge(
            PlatformMetadata(key="showcase.seed.version", value="command-center-showcase-v1")
        )
        for shipment_index, shipment in enumerate(SHOWCASE_SHIPMENTS):
            correlation_id = showcase_uuid("correlation", shipment.slug)
            event_ids = []
            for reading_index, temperature in enumerate(shipment.temperatures):
                event_id = showcase_uuid("telemetry", f"{shipment.slug}:{reading_index}")
                event_ids.append(event_id)
                occurred_at = generated_at - timedelta(
                    minutes=(len(shipment.temperatures) - reading_index) * 10 + shipment_index
                )
                above_limit = temperature > shipment.permitted_max
                await session.merge(
                    TelemetryRecord(
                        event_id=event_id,
                        shipment_id=shipment.shipment_id,
                        correlation_id=correlation_id,
                        occurred_at=occurred_at,
                        reading_sequence=reading_index + 1,
                        temperature_celsius=temperature,
                        cargo_type=shipment.cargo_type,
                        disposition="BREACH" if above_limit else "ACCEPTED",
                        policy_version="temperature-policy-v1",
                        policy_inputs={
                            "lowerThresholdCelsius": shipment.permitted_min,
                            "upperThresholdCelsius": shipment.permitted_max,
                            "clearlyUnsafeCelsius": shipment.permitted_max + 3.0,
                        },
                        reason_codes=(
                            ["CLEARLY_UNSAFE_TEMPERATURE"]
                            if temperature >= shipment.permitted_max + 3.0
                            else ["SUSTAINED_HIGH_TEMPERATURE"]
                            if above_limit
                            else []
                        ),
                        processed_at=generated_at,
                    )
                )
                telemetry_count += 1

            incident_id = shipment.incident_id
            if incident_id is None:
                continue
            if (
                shipment.incident_state is None
                or shipment.incident_severity is None
                or shipment.incident_age_minutes is None
                or shipment.recommendation_action is None
                or shipment.recommendation_expiry_minutes is None
            ):
                raise ValueError(f"incomplete showcase incident specification: {shipment.slug}")
            incident_count += 1
            pending_count += shipment.incident_state == "AWAITING_APPROVAL"
            created_at = generated_at - timedelta(minutes=shipment.incident_age_minutes)
            updated_at = (
                generated_at - timedelta(minutes=8)
                if shipment.incident_state == "RESOLVED"
                else created_at
            )
            evidence_id = showcase_uuid("evidence", shipment.slug)
            recommendation_id = showcase_uuid("recommendation", shipment.slug)
            evaluation_id = showcase_uuid("governance", shipment.slug)
            citations = _showcase_citations(shipment.recommendation_action, as_of=created_at)
            cited_chunk_ids = [chunk.chunk_id for chunk, _, _ in citations]
            await session.merge(
                IncidentRecord(
                    incident_id=incident_id,
                    shipment_id=shipment.shipment_id,
                    state=shipment.incident_state,
                    severity=shipment.incident_severity,
                    policy_version="temperature-policy-v1",
                    source_event_ids=[str(item) for item in event_ids],
                    correlation_id=correlation_id,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
            # merge() calls do not establish ORM relationship edges between these
            # independently constructed records. Persist the parent before its
            # evidence and recommendation foreign keys are considered.
            await session.flush()
            evidence_summary = (
                f"Canonical showcase telemetry for {shipment.reference}; "
                "no external model or operational command was used."
            )
            await session.merge(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    incident_id=incident_id,
                    telemetry_event_ids=[str(item) for item in event_ids],
                    policy_inputs={
                        "lowerThresholdCelsius": shipment.permitted_min,
                        "upperThresholdCelsius": shipment.permitted_max,
                    },
                    summary=evidence_summary,
                    content_hash=hashlib.sha256(evidence_summary.encode()).hexdigest(),
                    captured_at=created_at + timedelta(minutes=1),
                )
            )
            await session.merge(
                RecommendationRecord(
                    recommendation_id=recommendation_id,
                    incident_id=incident_id,
                    evidence_ids=[str(evidence_id)],
                    action_type=shipment.recommendation_action,
                    parameters={"shipmentReference": shipment.reference},
                    provider="deterministic",
                    author_identity="service:deterministic-recommendation-provider",
                    rationale="Deterministic local recommendation from bounded showcase evidence.",
                    expires_at=generated_at
                    + timedelta(minutes=shipment.recommendation_expiry_minutes),
                    non_authoritative=True,
                    provenance={
                        "provider": "deterministic",
                        "model": "deterministic-local-1.0",
                        "mode": "local",
                        "fallbackUsed": False,
                        "promptVersion": "governed-recommendation-v1",
                        "responseSchemaVersion": "1.0",
                        "evidenceSufficient": True,
                        "uncertaintyLevel": "low",
                        "missingInformation": [],
                        "contraindications": [],
                        "validationStatus": "valid",
                        "retrievedChunkIds": cited_chunk_ids,
                        "citedChunkIds": cited_chunk_ids,
                        "citedDocumentIds": [chunk.document_id for chunk, _, _ in citations],
                        "citedSectionIds": [chunk.section_id for chunk, _, _ in citations],
                        "sopCorpusVersion": CORPUS_VERSION,
                        "citationApplicability": {
                            chunk.chunk_id: why for chunk, _, why in citations
                        },
                    },
                )
            )
            await session.flush()
            governance_decision = (
                "APPROVAL_REQUIRED" if shipment.incident_state == "AWAITING_APPROVAL" else "ALLOWED"
            )
            await session.merge(
                GovernanceRecord(
                    evaluation_id=evaluation_id,
                    incident_id=incident_id,
                    recommendation_id=recommendation_id,
                    decision=governance_decision,
                    policy_version="governance-policy-v1",
                    reason_codes=(
                        ["HUMAN_APPROVAL_REQUIRED"]
                        if governance_decision == "APPROVAL_REQUIRED"
                        else ["BOUNDED_ACTION_ALLOWED"]
                    ),
                    inputs={
                        "recommendationSchemaValid": True,
                        "evidenceSnapshotComplete": True,
                        "citationsRecognized": True,
                        "citationsTrusted": True,
                        "actionAllowed": True,
                        "recommendationExpired": False,
                        "killSwitchActive": False,
                        "humanApprovalRequired": governance_decision == "APPROVAL_REQUIRED",
                    },
                    evaluated_at=created_at + timedelta(minutes=2),
                )
            )
            await session.flush()
            audit_events = (
                (
                    "TELEMETRY_RECEIVED",
                    event_ids[-1],
                    {
                        "shipmentReference": shipment.reference,
                        "readingCount": len(event_ids),
                        "latestTemperatureCelsius": shipment.temperatures[-1],
                    },
                    created_at,
                ),
                (
                    "BREACH_POLICY_EVALUATED",
                    event_ids[-1],
                    {
                        "policyVersion": "temperature-policy-v1",
                        "outcome": "BREACH",
                        "reasonCodes": ["CLEARLY_UNSAFE_TEMPERATURE"]
                        if shipment.incident_severity == "CRITICAL"
                        else ["SUSTAINED_HIGH_TEMPERATURE"],
                    },
                    created_at + timedelta(seconds=15),
                ),
                (
                    "EVIDENCE_SNAPSHOT_CREATED",
                    evidence_id,
                    {
                        "evidenceId": str(evidence_id),
                        "contentHash": hashlib.sha256(evidence_summary.encode()).hexdigest(),
                        "summary": evidence_summary,
                    },
                    created_at + timedelta(minutes=1),
                ),
                (
                    "RECOMMENDATION_CREATED",
                    recommendation_id,
                    {
                        "recommendationId": str(recommendation_id),
                        "provider": "deterministic",
                        "actionType": shipment.recommendation_action,
                        "nonAuthoritative": True,
                    },
                    created_at + timedelta(minutes=1, seconds=30),
                ),
                (
                    "GOVERNANCE_EVALUATED",
                    evaluation_id,
                    {
                        "evaluationId": str(evaluation_id),
                        "decision": governance_decision,
                        "policyVersion": "governance-policy-v1",
                        "reasonCodes": ["HUMAN_APPROVAL_REQUIRED"]
                        if governance_decision == "APPROVAL_REQUIRED"
                        else ["BOUNDED_ACTION_ALLOWED"],
                    },
                    created_at + timedelta(minutes=2),
                ),
            )
            for event_type, causation_id, payload, occurred_at in audit_events:
                await append_audit_event(
                    session,
                    incident_id=incident_id,
                    event_type=event_type,
                    actor_id="service:canonical-showcase",
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    payload=payload,
                    component_version="canonical-showcase-seed-1.0",
                    audit_event_id=showcase_uuid("audit", f"{shipment.slug}:{event_type}"),
                    occurred_at=occurred_at,
                )

        stable_ids = [shipment.shipment_id for shipment in SHOWCASE_SHIPMENTS]
        stored_telemetry = await session.scalar(
            select(func.count())
            .select_from(TelemetryRecord)
            .where(TelemetryRecord.shipment_id.in_(stable_ids))
        )
        stored_incidents = await session.scalar(
            select(func.count())
            .select_from(IncidentRecord)
            .where(IncidentRecord.shipment_id.in_(stable_ids))
        )
    if stored_telemetry != telemetry_count or stored_incidents != incident_count:
        raise RuntimeError(
            "showcase seed did not converge on the canonical row counts: "
            f"telemetry={stored_telemetry}/{telemetry_count}, "
            f"incidents={stored_incidents}/{incident_count}"
        )
    return ShowcaseSeedResult(
        shipments=len(SHOWCASE_SHIPMENTS),
        telemetry_records=telemetry_count,
        incidents=incident_count,
        pending_reviews=pending_count,
    )


async def _run() -> None:
    settings = get_settings()
    database = build_database(
        settings.database_url.get_secret_value() if settings.database_url else None,
        settings.database_connect_timeout_seconds,
    )
    if database is None:
        raise RuntimeError("COLDCHAIN_DATABASE_URL is required to prepare the showcase")
    try:
        result = await prepare_showcase(database)
        print(
            "Showcase prepared: "
            f"{result.shipments} shipments, {result.telemetry_records} telemetry rows, "
            f"{result.incidents} incidents, {result.pending_reviews} pending reviews"
        )
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(_run())
