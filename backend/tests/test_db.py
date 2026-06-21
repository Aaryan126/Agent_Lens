from agentlens.db import AuditEventRecord, Base, GateRecord, SessionRecord, TraceRecord


def test_postgres_metadata_contains_ledger_tables() -> None:
    assert {
        "agentlens_sessions",
        "agentlens_traces",
        "agentlens_gates",
        "agentlens_audit_events",
    }.issubset(Base.metadata.tables.keys())


def test_gate_record_has_query_indexes() -> None:
    indexes = {index.name for index in GateRecord.__table__.indexes}
    assert any("session_id" in str(index) for index in indexes)
    assert any("status" in str(index) for index in indexes)


def test_records_use_json_payload_columns() -> None:
    assert "payload" in SessionRecord.__table__.columns
    assert "payload" in TraceRecord.__table__.columns
    assert "payload" in GateRecord.__table__.columns
    assert "payload" in AuditEventRecord.__table__.columns
