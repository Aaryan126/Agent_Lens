from agentlens.config import Settings
from agentlens.model_routing import ModelRouter
from agentlens.schemas import PolicyAction, RiskLevel, ToolCallProposal


def test_low_risk_auto_execute_uses_nano_model() -> None:
    router = ModelRouter(Settings(openai_model="strong-model", openai_nano_model="nano-model"))
    proposal = ToolCallProposal(session_id="ses_test", tool_name="fs.read", params={"path": "prd.md"})

    role = router.role_for_intelligence(proposal, RiskLevel.LOW, PolicyAction.AUTO_EXECUTE)

    assert role == "nano"
    assert router.model_for(role) == "nano-model"


def test_gated_write_uses_strong_model() -> None:
    router = ModelRouter(Settings(openai_model="strong-model", openai_nano_model="nano-model"))
    proposal = ToolCallProposal(session_id="ses_test", tool_name="fs.write", params={"path": "app.py"})

    role = router.role_for_intelligence(proposal, RiskLevel.MEDIUM, PolicyAction.REQUIRE_APPROVAL)

    assert role == "strong"
    assert router.model_for(role) == "strong-model"
