"""Pure framework-independent domain types and policies."""

from coldchain.domain.breach import (
    BreachDisposition,
    BreachEvaluation,
    FreshPerishablePolicy,
    TemperatureReading,
)
from coldchain.domain.incidents import (
    ActionResult,
    Approval,
    ApprovalDecision,
    AuditEvent,
    Command,
    EvidenceSnapshot,
    GovernanceEvaluation,
    Incident,
    IncidentState,
    InvalidStateTransition,
    Recommendation,
    transition,
)

__all__ = [
    "ActionResult",
    "Approval",
    "ApprovalDecision",
    "AuditEvent",
    "BreachDisposition",
    "BreachEvaluation",
    "Command",
    "EvidenceSnapshot",
    "FreshPerishablePolicy",
    "GovernanceEvaluation",
    "Incident",
    "IncidentState",
    "InvalidStateTransition",
    "Recommendation",
    "TemperatureReading",
    "transition",
]
