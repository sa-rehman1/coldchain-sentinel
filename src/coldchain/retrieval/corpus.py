"""Load and validate the repository-owned SOP corpus."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from coldchain.retrieval.core import SopDocument

CORPUS_VERSION = "1.0.0"
DEFAULT_CORPUS = Path(__file__).parents[3] / "sop" / "coldchain-sop-corpus-v1.json"


def load_corpus(path: Path = DEFAULT_CORPUS) -> tuple[SopDocument, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("corpus_version") != CORPUS_VERSION:
        raise ValueError("unsupported SOP corpus version")
    return tuple(_document(item) for item in raw["documents"])


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
