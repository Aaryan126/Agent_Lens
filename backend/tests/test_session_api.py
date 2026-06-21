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


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

