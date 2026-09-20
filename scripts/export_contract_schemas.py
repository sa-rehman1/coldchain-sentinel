"""Export deterministic JSON Schema snapshots from Pydantic contracts."""

import json
from pathlib import Path

from coldchain.ai.models import RecommendationOutput, RecommendationProvenance
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

SCHEMAS = {
    "action-command.v1": ActionCommand,
    "approval-decision.v1": ApprovalDecision,
    "audit-event.v1": AuditEvent,
    "evidence-item.v1": EvidenceItem,
    "failure-envelope.v1": FailureEnvelope,
    "incident.v1": Incident,
    "recommendation.v1": Recommendation,
    "telemetry-event.v1": TelemetryEvent,
    "ai-recommendation-output.v1": RecommendationOutput,
    "recommendation-provenance.v1": RecommendationProvenance,
}


def main() -> None:
    destination = Path("contracts/schemas")
    destination.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMAS.items():
        schema = model.model_json_schema(by_alias=True, mode="validation")
        schema["$id"] = f"https://coldchain-sentinel.local/contracts/{name}.json"
        schema["title"] = name
        output = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        (destination / f"{name}.json").write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
