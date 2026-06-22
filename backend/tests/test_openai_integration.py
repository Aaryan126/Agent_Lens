import pytest

from agentlens.config import load_settings
from agentlens.intelligence import IntelligenceLayer
from agentlens.schemas import (
    BlastRadius,
    DecisionContext,
    GitSnapshot,
    PolicyAction,
    PolicyDecision,
    Reversibility,
    RiskAssessment,
    RiskLevel,
    SessionGoalSummary,
    ToolCallProposal,
)


@pytest.mark.integration
def test_real_openai_trajectory_structured_output() -> None:
    settings = load_settings()
    if not settings.has_openai_key:
        pytest.skip("OPENAI_API_KEY is required for real OpenAI integration tests")

    layer = IntelligenceLayer(settings)
    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="fs.write",
        params={"path": "src/auth/reset.py"},
        stated_reason="Patch reset token expiry check.",
        confidence=0.82,
    )
    risk = RiskAssessment(
        proposal_id=proposal.id,
        reversibility=Reversibility.MEDIUM,
        blast_radius=BlastRadius.MEDIUM,
        risk_level=RiskLevel.MEDIUM,
        recommended_action=PolicyAction.REQUIRE_APPROVAL,
        evidence=["auth reset code is part of a user-facing flow"],
        affected_files=["src/auth/reset.py"],
    )
    context = DecisionContext(
        session_id="ses_test",
        original_instruction="Fix the password reset bug without rebuilding auth.",
        proposal=proposal,
        risk=risk,
        policy=PolicyDecision(
            proposal_id=proposal.id,
            action=PolicyAction.REQUIRE_APPROVAL,
            reason="used semantic risk recommendation",
        ),
        git_snapshot=GitSnapshot(),
        session_goal=SessionGoalSummary(
            inferred_goal="Fix the password reset bug without rebuilding auth."
        ),
    )
    prediction = layer.trajectory(
        context,
    )
    assert prediction.next_steps
    assert 0 <= prediction.confidence <= 1


@pytest.mark.integration
def test_real_openai_builds_intelligence_card() -> None:
    settings = load_settings()
    if not settings.has_openai_key:
        pytest.skip("OPENAI_API_KEY is required for real OpenAI integration tests")

    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="fs.delete",
        params={"path": "backend/migrations/001_sessions.py"},
        stated_reason="The migration appears redundant.",
        confidence=0.58,
    )
    risk = RiskAssessment(
        proposal_id=proposal.id,
        reversibility=Reversibility.HIGH,
        blast_radius=BlastRadius.HIGH,
        risk_level=RiskLevel.CRITICAL,
        recommended_action=PolicyAction.BLOCK_AND_ALERT,
        evidence=["migration files are protected and may affect database state"],
        affected_files=["backend/migrations/001_sessions.py"],
    )

    context = DecisionContext(
        session_id="ses_test",
        original_instruction="Implement AgentLens without deleting migrations.",
        proposal=proposal,
        risk=risk,
        policy=PolicyDecision(
            proposal_id=proposal.id,
            action=PolicyAction.BLOCK_AND_ALERT,
            matched_policy="protect migrations and production",
            reason="matched policy: protect migrations and production",
        ),
        git_snapshot=GitSnapshot(),
        session_goal=SessionGoalSummary(
            inferred_goal="Implement AgentLens without deleting migrations.",
            recent_actions=["read requirements", "started implementing backend scaffolding"],
        ),
    )
    card = IntelligenceLayer(settings).build_card(context)
    assert card.summary
    assert card.risk_badge == RiskLevel.CRITICAL
    assert 0 <= card.confidence <= 1
    assert "Commitment point:" in card.trajectory_preview
