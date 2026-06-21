from pathlib import Path

from agentlens.analytics import build_ledger_analytics
from agentlens.schemas import SessionStart, ToolCallProposal
from agentlens.session import AgentLensSession
from agentlens.storage import InMemoryStore


def test_ledger_analytics_counts_trust_and_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    storage = InMemoryStore()
    session = AgentLensSession.start(
        SessionStart(original_instruction="Review risky changes.", repo_path=str(tmp_path)),
        storage=storage,
    )
    session.propose(
        ToolCallProposal(
            session_id=session.session.id,
            tool_name="fs.read",
            params={"path": "README.md"},
            confidence=0.9,
        )
    )
    risky_gate = session.propose(
        ToolCallProposal(
            session_id=session.session.id,
            tool_name="fs.delete",
            params={"path": "backend/migrations/001_sessions.py"},
            confidence=0.5,
        )
    )
    assert risky_gate.intelligence_card is not None
    risky_gate.intelligence_card.drift_flag = "Possible drift."
    storage.update_gate(risky_gate)

    analytics = build_ledger_analytics(session.session.id, session.timeline().gates)

    assert analytics.trust_score.total_actions == 2
    assert analytics.trust_score.auto_executed == 1
    assert analytics.trust_score.human_interventions == 1
    assert analytics.trust_score.score == 0.5
    assert len(analytics.drift_history) == 1
