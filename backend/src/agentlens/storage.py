from __future__ import annotations

from threading import RLock

from agentlens.audit import AuditLog, JsonlAuditLog, NullAuditLog
from agentlens.config import load_settings
from agentlens.schemas import Gate, Session, TraceEvent


class InMemoryStore:
    """Small append-only store for local demos and tests."""

    def __init__(self, audit_log: AuditLog | None = None) -> None:
        self._lock = RLock()
        self.audit_log = audit_log or NullAuditLog()
        self.sessions: dict[str, Session] = {}
        self.traces: list[TraceEvent] = []
        self.gates: dict[str, Gate] = {}

    def add_session(self, session: Session) -> Session:
        with self._lock:
            self.sessions[session.id] = session
            self.audit_log.append("session_started", session)
        return session

    def get_session(self, session_id: str) -> Session:
        with self._lock:
            return self.sessions[session_id]

    def add_trace(self, event: TraceEvent) -> TraceEvent:
        with self._lock:
            self.traces.append(event)
            self.audit_log.append("trace_captured", event)
        return event

    def add_gate(self, gate: Gate) -> Gate:
        with self._lock:
            self.gates[gate.id] = gate
            self.audit_log.append("gate_created", gate)
        return gate

    def update_gate(self, gate: Gate) -> Gate:
        with self._lock:
            self.gates[gate.id] = gate
            self.audit_log.append("gate_updated", gate)
        return gate

    def pending_gates(self) -> list[Gate]:
        with self._lock:
            return [gate for gate in self.gates.values() if gate.status == "pending"]

    def timeline(self, session_id: str) -> tuple[list[TraceEvent], list[Gate]]:
        with self._lock:
            traces = [event for event in self.traces if event.session_id == session_id]
            gates = [gate for gate in self.gates.values() if gate.session_id == session_id]
        return traces, gates

    def clear(self) -> None:
        with self._lock:
            self.sessions.clear()
            self.traces.clear()
            self.gates.clear()


def create_default_store() -> InMemoryStore:
    settings = load_settings()
    return InMemoryStore(audit_log=JsonlAuditLog(settings.agentlens_audit_log_path))


store = create_default_store()
