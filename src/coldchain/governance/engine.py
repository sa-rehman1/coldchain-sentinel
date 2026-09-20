"""Default deterministic governance evaluator."""

from coldchain.domain.governance import (
    ActionRequest,
    GovernanceDecision,
    GovernancePolicy,
    GovernanceResult,
)


class DeterministicGovernanceEngine:
    """Classify requested actions without consulting an LLM."""

    def evaluate(self, request: ActionRequest, policy: GovernancePolicy) -> GovernanceResult:
        action = request.action_type
        if policy.kill_switch_active:
            return GovernanceResult(
                decision=GovernanceDecision.KILL_SWITCH_ACTIVE,
                policy_version=policy.version,
                reason="the operational kill switch is active",
            )
        if action in policy.prohibited_actions:
            return GovernanceResult(
                decision=GovernanceDecision.PROHIBITED,
                policy_version=policy.version,
                reason="the requested action is explicitly prohibited",
            )
        if action in policy.approval_required_actions:
            return GovernanceResult(
                decision=GovernanceDecision.APPROVAL_REQUIRED,
                policy_version=policy.version,
                reason="the requested action requires authenticated human approval",
            )
        if action in policy.allowed_actions:
            return GovernanceResult(
                decision=GovernanceDecision.ALLOWED,
                policy_version=policy.version,
                reason="the requested action is allowlisted",
            )
        return GovernanceResult(
            decision=GovernanceDecision.PROHIBITED,
            policy_version=policy.version,
            reason="the requested action is not present in an allowlist",
        )
