from pathlib import Path

from fastapi.testclient import TestClient

from agentlens.api import app
from agentlens.schemas import SessionStart, ToolCallProposal
from agentlens.session import AgentLensSession
from agentlens.storage import InMemoryStore


def test_session_trace_gate_flow(tmp_path: Path) -> None:
    storage = InMemoryStore()
    session = AgentLensSession.start(
        SessionStart(original_instruction="Read the PRD.", repo_path=str(tmp_path)),
        storage=storage,
    )
    gate = session.propose(
        ToolCallProposal(
            session_id=session.session.id,
            tool_name="fs.read",
            params={"path": "prd.md"},
            confidence=0.95,
        )
    )
    timeline = session.timeline()
    assert gate.status == "auto_executed"
    assert len(timeline.traces) == 1
    assert len(timeline.gates) == 1


def test_fallback_card_is_used_without_openai_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    storage = InMemoryStore()
    session = AgentLensSession.start(
        SessionStart(original_instruction="Delete nothing risky.", repo_path=str(tmp_path)),
        storage=storage,
    )
    gate = session.propose(
        ToolCallProposal(
            session_id=session.session.id,
            tool_name="fs.write",
            params={"path": "notes.md"},
            confidence=0.8,
        )
    )
    assert gate.intelligence_card is not None
    assert "Agent wants to run fs.write" in gate.intelligence_card.summary
    assert "OpenAI intelligence is configured" in gate.intelligence_card.trajectory_preview


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_demo_session_endpoint_creates_reviewable_gates(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    client = TestClient(app)
    response = client.post("/demo/session")
    assert response.status_code == 200
    body = response.json()
    assert body["session"]["id"].startswith("ses_")
    assert body["gates"]
    assert body["timeline"]["traces"]


def test_session_analytics_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    client = TestClient(app)
    response = client.post("/demo/session")
    assert response.status_code == 200
    session_id = response.json()["session"]["id"]

    analytics_response = client.get(f"/sessions/{session_id}/analytics")

    assert analytics_response.status_code == 200
    body = analytics_response.json()
    assert body["session_id"] == session_id
    assert body["trust_score"]["total_actions"] >= 1
    assert body["risk_distribution"]


def test_gate_decision_endpoint_resolves_pending_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    client = TestClient(app)
    session_response = client.post(
        "/sessions",
        json={"original_instruction": "Review writes.", "repo_path": str(tmp_path)},
    )
    session_id = session_response.json()["id"]
    proposal_response = client.post(
        f"/sessions/{session_id}/tool-calls",
        json={
            "session_id": session_id,
            "tool_name": "fs.write",
            "params": {"path": "notes.md"},
            "confidence": 0.8,
        },
    )
    gate = proposal_response.json()
    assert gate["status"] == "pending"

    decision_response = client.post(
        f"/gates/{gate['id']}/approve",
        json={"reason": "Scoped write is acceptable."},
    )
    assert decision_response.status_code == 200
    resolved = decision_response.json()
    assert resolved["status"] == "approved"
    assert resolved["human_reason"] == "Scoped write is acceptable."
