import pytest

from coldchain.domain.governance import (
    ActionRequest,
    GovernanceDecision,
    GovernancePolicy,
)
from coldchain.governance.engine import DeterministicGovernanceEngine


@pytest.fixture
def policy() -> GovernancePolicy:
    return GovernancePolicy(
        version="governance-1.0",
        allowed_actions=frozenset({"ADD_NOTE"}),
        approval_required_actions=frozenset({"CONTACT_DRIVER"}),
        prohibited_actions=frozenset({"DISABLE_REFRIGERATION"}),
    )


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("ADD_NOTE", GovernanceDecision.ALLOWED),
        ("CONTACT_DRIVER", GovernanceDecision.APPROVAL_REQUIRED),
        ("DISABLE_REFRIGERATION", GovernanceDecision.PROHIBITED),
        ("UNKNOWN_ACTION", GovernanceDecision.PROHIBITED),
    ],
)
def test_governance_classification(
    policy: GovernancePolicy, action: str, expected: GovernanceDecision
) -> None:
    result = DeterministicGovernanceEngine().evaluate(ActionRequest(action), policy)
    assert result.decision is expected
    assert result.policy_version == policy.version


def test_kill_switch_takes_precedence(policy: GovernancePolicy) -> None:
    stopped = GovernancePolicy(
        version=policy.version,
        allowed_actions=policy.allowed_actions,
        approval_required_actions=policy.approval_required_actions,
        prohibited_actions=policy.prohibited_actions,
        kill_switch_active=True,
    )
    result = DeterministicGovernanceEngine().evaluate(ActionRequest("ADD_NOTE"), stopped)
    assert result.decision is GovernanceDecision.KILL_SWITCH_ACTIVE
