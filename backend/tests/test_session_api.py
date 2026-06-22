from pathlib import Path

from fastapi.testclient import TestClient

from agentlens.adapters.codex_cli import CodexExecResult
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


def test_latest_session_endpoint_returns_newest_session(tmp_path: Path) -> None:
    client = TestClient(app)
    first = client.post(
        "/sessions",
        json={"original_instruction": "First session.", "repo_path": str(tmp_path)},
    ).json()
    second = client.post(
        "/sessions",
        json={"original_instruction": "Second session.", "repo_path": str(tmp_path)},
    ).json()

    response = client.get("/sessions/latest")

    assert response.status_code == 200
    assert response.json()["id"] in {first["id"], second["id"]}
    assert response.json()["id"] == second["id"]


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


def test_audit_events_endpoint_returns_recent_events(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    client = TestClient(app)
    client.post("/demo/session")

    response = client.get("/audit/events?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body["events"]) <= 2
    assert body["events"]


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


def test_explain_gate_endpoint_returns_intelligence_evidence(tmp_path: Path, monkeypatch) -> None:
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
        },
    )
    gate = proposal_response.json()

    response = client.post(f"/gates/{gate['id']}/explain")

    assert response.status_code == 200
    body = response.json()
    assert body["gate_id"] == gate["id"]
    assert body["risk"]["risk_level"] == "medium"
    assert body["confidence_evidence"]
    assert body["suggested_modification"]


def test_codex_session_endpoint_runs_adapter_and_gates_proposals(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")

    def fake_run(self, **kwargs):
        return CodexExecResult(
            returncode=0,
            stdout="",
            stderr="",
            proposals=[
                ToolCallProposal(
                    session_id=kwargs["session_id"],
                    tool_name="fs.read",
                    params={"path": "prd.md"},
                    stated_reason="Need requirements context.",
                )
            ],
        )

    monkeypatch.setattr("agentlens.api.CodexCliAdapter.run", fake_run)
    client = TestClient(app)

    response = client.post(
        "/codex/sessions",
        json={
            "prompt": "Inspect the PRD.",
            "repo_path": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["original_instruction"] == "Inspect the PRD."
    assert body["timeline"]["traces"][0]["tool_name"] == "fs.read"
    assert body["gates"][0]["status"] == "auto_executed"
