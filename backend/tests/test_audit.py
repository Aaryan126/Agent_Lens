from agentlens.audit import JsonlAuditLog
from agentlens.schemas import SessionStart, ToolCallProposal
from agentlens.session import AgentLensSession
from agentlens.storage import InMemoryStore


def test_jsonl_audit_log_records_session_trace_and_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    audit = JsonlAuditLog(tmp_path / "audit.jsonl")
    store = InMemoryStore(audit_log=audit)
    session = AgentLensSession.start(
        SessionStart(original_instruction="Read safely.", repo_path=str(tmp_path)),
        storage=store,
    )
    session.propose(
        ToolCallProposal(
            session_id=session.session.id,
            tool_name="fs.read",
            params={"path": "README.md"},
            confidence=0.9,
        )
    )

    event_types = [record["event_type"] for record in audit.read_all()]

    assert event_types == ["session_started", "trace_captured", "gate_created"]
