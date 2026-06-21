from __future__ import annotations

from threading import RLock

from agentlens.schemas import Gate, Session, TraceEvent


class InMemoryStore:
    """Small append-only store for local demos and tests."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.sessions: dict[str, Session] = {}
        self.traces: list[TraceEvent] = []
        self.gates: dict[str, Gate] = {}

    def add_session(self, session: Session) -> Session:
        with self._lock:
            self.sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Session:
        with self._lock:
            return self.sessions[session_id]

    def add_trace(self, event: TraceEvent) -> TraceEvent:
        with self._lock:
            self.traces.append(event)
        return event

    def add_gate(self, gate: Gate) -> Gate:
        with self._lock:
            self.gates[gate.id] = gate
        return gate

    def update_gate(self, gate: Gate) -> Gate:
        with self._lock:
            self.gates[gate.id] = gate
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


store = InMemoryStore()
