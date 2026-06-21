from __future__ import annotations

from agentlens.config import AgentLensConfig
from agentlens.schemas import PolicyAction, PolicyDecision, RiskAssessment, ToolCallProposal


class PolicyEngine:
    def __init__(self, config: AgentLensConfig) -> None:
        self.config = config

    def evaluate(
        self, proposal: ToolCallProposal, risk_assessment: RiskAssessment | None = None
    ) -> PolicyDecision:
        risk_level = risk_assessment.risk_level if risk_assessment else None
        for policy in self.config.policies:
            if policy.matches(proposal, risk_level=risk_level):
                return PolicyDecision(
                    proposal_id=proposal.id,
                    action=policy.action,
                    matched_policy=policy.name,
                    reason=f"matched policy: {policy.name}",
                )

        if risk_assessment is not None:
            return PolicyDecision(
                proposal_id=proposal.id,
                action=risk_assessment.recommended_action,
                matched_policy=None,
                reason="used semantic risk recommendation",
            )

        return PolicyDecision(
            proposal_id=proposal.id,
            action=PolicyAction.REQUIRE_APPROVAL,
            matched_policy=None,
            reason="no matching policy",
        )

