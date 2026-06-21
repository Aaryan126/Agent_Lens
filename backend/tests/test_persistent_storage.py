from __future__ import annotations

import asyncio
from pathlib import Path

from agentlens.schemas import GateStatus, Session, SessionStart, ToolCallProposal
from agentlens.session import AgentLensSession
from agentlens.storage import DatabaseBackedStore, run_blocking


def test_database_backed_store_mirrors_session_trace_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    repository = FakeLedgerRepository()
    storage = DatabaseBackedStore(repository)
    session = AgentLensSession.start(
        SessionStart(original_instruction="Read safely.", repo_path=str(tmp_path)),
        storage=storage,
    )

    gate = session.propose(
        ToolCallProposal(
            session_id=session.session.id,
            tool_name="fs.read",
            params={"path": "README.md"},
            confidence=0.9,
        )
    )

    assert repository.sessions[0].id == session.session.id
    assert repository.traces[0].proposal_id == gate.proposal_id
    assert repository.gates[0].id == gate.id
    assert [event["event_type"] for event in repository.audit_events] == [
        "session_started",
        "trace_captured",
        "gate_created",
    ]


def test_database_backed_store_reloads_existing_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    repository = FakeLedgerRepository()
    first_store = DatabaseBackedStore(repository)
    session = AgentLensSession.start(
        SessionStart(original_instruction="Review writes.", repo_path=str(tmp_path)),
        storage=first_store,
    )
    gate = session.propose(
        ToolCallProposal(
            session_id=session.session.id,
            tool_name="fs.write",
            params={"path": "notes.md"},
            confidence=0.8,
        )
    )
    gate.status = GateStatus.APPROVED
    first_store.update_gate(gate)

    reloaded_store = DatabaseBackedStore(repository)
    traces, gates = reloaded_store.timeline(session.session.id)

    assert reloaded_store.get_session(session.session.id).id == session.session.id
    assert len(traces) == 1
    assert gates[0].status == GateStatus.APPROVED


def test_run_blocking_works_inside_existing_event_loop() -> None:
    async def outer() -> str:
        return run_blocking(_async_value())

    assert asyncio.run(outer()) == "ok"


async def _async_value() -> str:
    return "ok"


class FakeLedgerRepository:
    def __init__(self) -> None:
        self.sessions: list[Session] = []
        self.traces = []
        self.gates = []
        self.audit_events = []

    async def list_sessions(self):
        return list(self.sessions)

    async def list_traces(self):
        return list(self.traces)

    async def list_gates(self):
        return list(self.gates)

    async def add_session(self, session):
        self.sessions.append(session)

    async def add_trace(self, trace):
        self.traces.append(trace)

    async def upsert_gate(self, gate):
        self.gates = [existing for existing in self.gates if existing.id != gate.id]
        self.gates.append(gate.model_copy(deep=True))

    async def add_audit_event(self, event_type, payload):
        self.audit_events.append({"event_type": event_type, "payload": payload})

    async def list_audit_events(self):
        return list(self.audit_events)
