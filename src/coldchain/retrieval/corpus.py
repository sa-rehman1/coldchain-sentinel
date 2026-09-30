"""Load and validate the repository-owned SOP corpus."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from coldchain.retrieval.core import SopChunk, SopDocument, chunk_document

CORPUS_VERSION = "1.0.0"
DEFAULT_CORPUS = Path(__file__).parents[3] / "sop" / "coldchain-sop-corpus-v1.json"
SECTION_TITLES = {
    "TEMP-001-S1": "Deterministic excursion evaluation",
    "TEMP-001-S2": "Evidence-preserving shipment hold",
    "EVID-001-S1": "Required immutable evidence",
    "EVID-001-S2": "Sensor integrity verification",
    "EVID-001-S3": "Stale or missing telemetry",
    "REEFER-001-S1": "Malfunction indicators",
    "REEFER-001-S2": "Escalation and inspection",
    "HOLD-001-S1": "Dispatcher authorization boundary",
    "HOLD-001-S2": "Inspection requirements",
    "HOLD-001-S3": "Release requirements",
    "ESC-001-S1": "Escalation levels",
    "ESC-001-S2": "Dispatcher responsibilities",
    "GOV-001-S1": "Automation prohibitions",
    "GOV-001-S2": "Provider failure fallback",
}
SECTION_APPLICABILITY = {
    "TEMP-001-S2": (
        "This section defines how to respond to a sustained fresh-product temperature "
        "breach and requires preserving the shipment pending review."
    ),
    "EVID-001-S1": (
        "This section defines the telemetry, sensor, timing, sequence, and integrity "
        "evidence required before a decision."
    ),
    "HOLD-001-S1": (
        "This section requires authenticated dispatcher authorization for HOLD_SHIPMENT "
        "and prevents the recommendation engine from executing it directly."
    ),
}


@dataclass(frozen=True, slots=True)
class TrustedSopCitation:
    chunk_id: str
    document_id: str
    document_title: str
    document_version: str
    section_id: str
    section_title: str
    effective_date: date
    excerpt: str
    why_applicable: str
    validation_status: str


def load_corpus(path: Path = DEFAULT_CORPUS) -> tuple[SopDocument, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("corpus_version") != CORPUS_VERSION:
        raise ValueError("unsupported SOP corpus version")
    return tuple(_document(item) for item in raw["documents"])


def resolve_trusted_citations(
    chunk_ids: tuple[str, ...],
    *,
    as_of: date,
    applicability: dict[str, str] | None = None,
    path: Path = DEFAULT_CORPUS,
) -> tuple[TrustedSopCitation, ...]:
    """Resolve only effective, non-superseded chunks from the authored corpus."""

    documents = load_corpus(path)
    titles = {item.document_id: item.title for item in documents}
    versions = {item.document_id: item.semantic_version for item in documents}
    chunks: dict[str, SopChunk] = {
        chunk.chunk_id: chunk for document in documents for chunk in chunk_document(document)
    }
    reasons = applicability or {}
    resolved: list[TrustedSopCitation] = []
    for chunk_id in chunk_ids:
        chunk = chunks.get(chunk_id)
        if chunk is None or chunk.effective_date > as_of:
            continue
        if chunk.superseded_date is not None and chunk.superseded_date <= as_of:
            continue
        resolved.append(
            TrustedSopCitation(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_title=titles[chunk.document_id],
                document_version=versions[chunk.document_id],
                section_id=chunk.section_id,
                section_title=SECTION_TITLES.get(chunk.section_id, chunk.section_id),
                effective_date=chunk.effective_date,
                excerpt=chunk.text,
                why_applicable=SECTION_APPLICABILITY.get(
                    chunk.section_id,
                    reasons.get(
                        chunk.chunk_id,
                        "This effective ColdChain Sentinel section governs the recorded incident.",
                    ),
                ),
                validation_status="trusted",
            )
        )
    return tuple(resolved)


def _document(item: dict[str, Any]) -> SopDocument:
    sections = tuple((section["section_id"], section["text"]) for section in item["sections"])
    canonical = json.dumps(item["sections"], sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(canonical.encode()).hexdigest()
    if checksum != item["checksum"]:
        raise ValueError(f"checksum mismatch for {item['document_id']}")
    return SopDocument(
        document_id=item["document_id"],
        title=item["title"],
        semantic_version=item["semantic_version"],
        effective_date=date.fromisoformat(item["effective_date"]),
        superseded_date=date.fromisoformat(item["superseded_date"])
        if item.get("superseded_date")
        else None,
        checksum=checksum,
        classification=item["classification"],
        author=item["author"],
        source=item["source"],
        schema_version=item["schema_version"],
        sections=sections,
    )
