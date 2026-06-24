from __future__ import annotations

import asyncio
from threading import RLock, Thread
from typing import Any, Coroutine

from pydantic import BaseModel

from agentlens.audit import AuditLog, JsonlAuditLog, NullAuditLog
from agentlens.config import load_settings
from agentlens.db import SqlAlchemyLedgerRepository, create_engine, create_sessionmaker
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


class DatabaseAuditLog(AuditLog):
    def __init__(self, repository: SqlAlchemyLedgerRepository) -> None:
        self.repository = repository

    def append(self, event_type: str, payload: BaseModel | dict[str, Any]) -> None:
        serialized = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
        run_blocking(self.repository.add_audit_event(event_type, serialized))

    def read_all(self) -> list[dict[str, Any]]:
        return run_blocking(self.repository.list_audit_events())


class DatabaseBackedStore(InMemoryStore):
    """In-memory working set mirrored to PostgreSQL for hosted demos."""

    def __init__(self, repository: SqlAlchemyLedgerRepository) -> None:
        self.repository = repository
        super().__init__(audit_log=DatabaseAuditLog(repository))
        self.reload()

    def reload(self) -> None:
        sessions = run_blocking(self.repository.list_sessions())
        traces = run_blocking(self.repository.list_traces())
        gates = run_blocking(self.repository.list_gates())
        with self._lock:
            self.sessions = {session.id: session for session in sessions}
            self.traces = traces
            self.gates = {gate.id: gate for gate in gates}

    def add_session(self, session: Session) -> Session:
        result = super().add_session(session)
        run_blocking(self.repository.add_session(session))
        return result

    def add_trace(self, event: TraceEvent) -> TraceEvent:
        result = super().add_trace(event)
        run_blocking(self.repository.add_trace(event))
        return result

    def add_gate(self, gate: Gate) -> Gate:
        result = super().add_gate(gate)
        run_blocking(self.repository.upsert_gate(gate))
        return result

    def update_gate(self, gate: Gate) -> Gate:
        result = super().update_gate(gate)
        run_blocking(self.repository.upsert_gate(gate))
        return result


class JsonlBackedStore(InMemoryStore):
    """In-memory working set restored from and mirrored to a local JSONL audit log."""

    def __init__(self, audit_log: JsonlAuditLog) -> None:
        super().__init__(audit_log=audit_log)
        self.reload()

    def reload(self) -> None:
        sessions: dict[str, Session] = {}
        traces_by_id: dict[str, TraceEvent] = {}
        gates: dict[str, Gate] = {}
        for record in self.audit_log.read_all():
            event_type = str(record.get("event_type") or "")
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            try:
                if event_type == "session_started":
                    session = Session.model_validate(payload)
                    sessions[session.id] = session
                elif event_type == "trace_captured":
                    trace = TraceEvent.model_validate(payload)
                    traces_by_id[trace.id] = trace
                elif event_type in {"gate_created", "gate_updated"}:
                    gate = Gate.model_validate(payload)
                    gates[gate.id] = gate
            except Exception:
                continue
        with self._lock:
            self.sessions = sessions
            self.traces = sorted(traces_by_id.values(), key=lambda trace: trace.created_at)
            self.gates = gates


def run_blocking(coroutine: Coroutine[Any, Any, Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result: dict[str, Any] = {}

    def target() -> None:
        try:
            result["value"] = asyncio.run(coroutine)
        except BaseException as exc:
            result["error"] = exc

    thread = Thread(target=target)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def create_default_store() -> InMemoryStore:
    settings = load_settings()
    if settings.agentlens_storage_backend == "postgres":
        engine = create_engine(settings.database_url)
        session_factory = create_sessionmaker(engine)
        repository = SqlAlchemyLedgerRepository(session_factory)
        run_blocking(repository.create_schema(engine))
        return DatabaseBackedStore(repository)
    if settings.agentlens_storage_backend == "local_jsonl":
        return JsonlBackedStore(JsonlAuditLog(settings.agentlens_audit_log_path))
    return InMemoryStore(audit_log=JsonlAuditLog(settings.agentlens_audit_log_path))


store = create_default_store()
