import pytest

from agentlens.config import load_settings
from agentlens.intelligence import IntelligenceLayer
from agentlens.schemas import ToolCallProposal


@pytest.mark.integration
def test_real_openai_trajectory_structured_output() -> None:
    settings = load_settings()
    if not settings.has_openai_key:
        pytest.skip("OPENAI_API_KEY is required for real OpenAI integration tests")

    layer = IntelligenceLayer(settings)
    prediction = layer.trajectory(
        "Fix the password reset bug without rebuilding auth.",
        ToolCallProposal(
            session_id="ses_test",
            tool_name="fs.write",
            params={"path": "src/auth/reset.py"},
            stated_reason="Patch reset token expiry check.",
            confidence=0.82,
        ),
    )
    assert prediction.next_steps
    assert 0 <= prediction.confidence <= 1
