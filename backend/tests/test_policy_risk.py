from pathlib import Path

from agentlens.config import AgentLensConfig, PolicyRule
from agentlens.policy import PolicyEngine
from agentlens.risk import SemanticRiskClassifier
from agentlens.schemas import PolicyAction, RiskLevel, ToolCallProposal


def test_safe_read_is_low_risk(tmp_path: Path) -> None:
    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="fs.read",
        params={"path": "README.md"},
        confidence=0.9,
    )
    risk = SemanticRiskClassifier(str(tmp_path)).assess(proposal)
    assert risk.risk_level == RiskLevel.LOW
    assert risk.recommended_action == PolicyAction.AUTO_EXECUTE


def test_migration_delete_is_high_or_critical(tmp_path: Path) -> None:
    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="fs.delete",
        params={"path": "backend/migrations/001_sessions.py"},
        confidence=0.58,
    )
    risk = SemanticRiskClassifier(str(tmp_path)).assess(proposal)
    assert risk.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert risk.recommended_action in {PolicyAction.REQUIRE_APPROVAL, PolicyAction.BLOCK_AND_ALERT}


def test_policy_precedence_over_risk() -> None:
    config = AgentLensConfig(
        policies=[
            PolicyRule(
                name="safe reads",
                condition={"tool_in": ["fs.read"]},
                action=PolicyAction.AUTO_EXECUTE,
            )
        ]
    )
    proposal = ToolCallProposal(session_id="ses_test", tool_name="fs.read", params={})
    decision = PolicyEngine(config).evaluate(proposal)
    assert decision.action == PolicyAction.AUTO_EXECUTE
    assert decision.matched_policy == "safe reads"

