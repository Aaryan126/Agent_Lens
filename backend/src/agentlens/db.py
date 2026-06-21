from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agentlens.schemas import Gate, Session, TraceEvent


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "agentlens_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    original_instruction: Mapped[str] = mapped_column(String, nullable=False)
    repo_path: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    team_id: Mapped[str] = mapped_column(String, nullable=False)
    config_path: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class TraceRecord(Base):
    __tablename__ = "agentlens_traces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    proposal_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    tool_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class GateRecord(Base):
    __tablename__ = "agentlens_gates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    proposal_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, index=True, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class AuditEventRecord(Base):
    __tablename__ = "agentlens_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(normalize_async_database_url(database_url))


def normalize_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


class SqlAlchemyLedgerRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_schema(self, engine: AsyncEngine) -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def add_session(self, session: Session) -> None:
        async with self.session_factory() as db:
            db.add(
                SessionRecord(
                    id=session.id,
                    original_instruction=session.original_instruction,
                    repo_path=session.repo_path,
                    user_id=session.user_id,
                    team_id=session.team_id,
                    config_path=session.config_path,
                    created_at=session.created_at,
                    payload=session.model_dump(mode="json"),
                )
            )
            await db.commit()

    async def list_sessions(self) -> list[Session]:
        async with self.session_factory() as db:
            records = (await db.scalars(select(SessionRecord))).all()
        return [Session.model_validate(record.payload) for record in records]

    async def add_trace(self, trace: TraceEvent) -> None:
        async with self.session_factory() as db:
            db.add(
                TraceRecord(
                    id=trace.id,
                    session_id=trace.session_id,
                    proposal_id=trace.proposal_id,
                    tool_name=trace.tool_name,
                    created_at=trace.created_at,
                    payload=trace.model_dump(mode="json"),
                )
            )
            await db.commit()

    async def list_traces(self) -> list[TraceEvent]:
        async with self.session_factory() as db:
            records = (await db.scalars(select(TraceRecord).order_by(TraceRecord.created_at))).all()
        return [TraceEvent.model_validate(record.payload) for record in records]

    async def upsert_gate(self, gate: Gate) -> None:
        async with self.session_factory() as db:
            existing = await db.get(GateRecord, gate.id)
            payload = gate.model_dump(mode="json")
            if existing is None:
                db.add(
                    GateRecord(
                        id=gate.id,
                        session_id=gate.session_id,
                        proposal_id=gate.proposal_id,
                        status=str(gate.status),
                        risk_level=str(gate.risk_assessment.risk_level),
                        created_at=gate.created_at,
                        resolved_at=gate.resolved_at,
                        payload=payload,
                    )
                )
            else:
                existing.status = str(gate.status)
                existing.risk_level = str(gate.risk_assessment.risk_level)
                existing.resolved_at = gate.resolved_at
                existing.payload = payload
            await db.commit()

    async def list_gates(self) -> list[Gate]:
        async with self.session_factory() as db:
            records = (await db.scalars(select(GateRecord).order_by(GateRecord.created_at))).all()
        return [Gate.model_validate(record.payload) for record in records]

    async def add_audit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        async with self.session_factory() as db:
            db.add(
                AuditEventRecord(
                    event_type=event_type,
                    created_at=datetime.now(UTC),
                    payload=payload,
                )
            )
            await db.commit()

    async def list_audit_events(self, limit: int | None = None) -> list[dict[str, Any]]:
        statement = select(AuditEventRecord).order_by(AuditEventRecord.created_at)
        if limit is not None:
            statement = statement.limit(limit)
        async with self.session_factory() as db:
            records = (await db.scalars(statement)).all()
        return [
            {
                "event_type": record.event_type,
                "created_at": record.created_at.isoformat(),
                "payload": record.payload,
            }
            for record in records
        ]
