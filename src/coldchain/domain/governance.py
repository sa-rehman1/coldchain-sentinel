"""Deterministic governance domain model."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class GovernanceDecision(StrEnum):
    ALLOWED = "ALLOWED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    PROHIBITED = "PROHIBITED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_type: str


@dataclass(frozen=True, slots=True)
class GovernancePolicy:
    version: str
    allowed_actions: frozenset[str]
    approval_required_actions: frozenset[str]
    prohibited_actions: frozenset[str]
    kill_switch_active: bool = False


@dataclass(frozen=True, slots=True)
class GovernanceResult:
    decision: GovernanceDecision
    policy_version: str
    reason: str


class GovernanceEvaluator(Protocol):
    def evaluate(self, request: ActionRequest, policy: GovernancePolicy) -> GovernanceResult: ...
