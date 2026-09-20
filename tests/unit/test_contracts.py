import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from coldchain.contracts import (
    ActionCommand,
    ApprovalDecision,
    AuditEvent,
    EvidenceItem,
    FailureEnvelope,
    Incident,
    Recommendation,
    TelemetryEvent,
)

ROOT = Path(__file__).parents[2]
CONTRACTS: dict[str, type[BaseModel]] = {
    "action-command.v1": ActionCommand,
    "approval-decision.v1": ApprovalDecision,
    "audit-event.v1": AuditEvent,
    "evidence-item.v1": EvidenceItem,
    "failure-envelope.v1": FailureEnvelope,
    "incident.v1": Incident,
    "recommendation.v1": Recommendation,
    "telemetry-event.v1": TelemetryEvent,
}


@pytest.mark.parametrize(("name", "model"), CONTRACTS.items())
def test_example_matches_model_and_committed_json_schema(name: str, model: type[BaseModel]) -> None:
    example: dict[str, Any] = json.loads(
        (ROOT / "contracts" / "examples" / f"{name}.json").read_text(encoding="utf-8")
    )
    schema: dict[str, Any] = json.loads(
        (ROOT / "contracts" / "schemas" / f"{name}.json").read_text(encoding="utf-8")
    )
    parsed = model.model_validate(example)
    assert parsed.model_dump(mode="json", by_alias=True) == example
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    generated = model.model_json_schema(by_alias=True, mode="validation")
    generated["$id"] = f"https://coldchain-sentinel.local/contracts/{name}.json"
    generated["title"] = name
    assert schema == generated


def test_naive_timestamps_are_rejected() -> None:
    example = json.loads(
        (ROOT / "contracts" / "examples" / "telemetry-event.v1.json").read_text(encoding="utf-8")
    )
    example["occurredAt"] = "2026-09-19T15:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        TelemetryEvent.model_validate(example)


def test_recommendation_cannot_claim_authority() -> None:
    example = json.loads(
        (ROOT / "contracts" / "examples" / "recommendation.v1.json").read_text(encoding="utf-8")
    )
    example["authorizationStatement"] = "AUTHORIZED"
    with pytest.raises(ValidationError):
        Recommendation.model_validate(example)
