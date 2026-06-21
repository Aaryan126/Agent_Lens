from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentlens.schemas import Gate, GateStatus, Session, SessionStart, Timeline, ToolCallProposal
from agentlens.session import AgentLensSession
from agentlens.simulator import default_demo_proposals
from agentlens.storage import store

app = FastAPI(title="AgentLens", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class DecisionPayload(BaseModel):
    reason: str | None = None
    modified_instruction: str | None = None


class DemoSessionResponse(BaseModel):
    session: Session
    gates: list[Gate]
    timeline: Timeline


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sessions")
def create_session(payload: SessionStart):
    session = AgentLensSession.start(payload)
    return session.session


@app.post("/demo/session")
def create_demo_session() -> DemoSessionResponse:
    session = AgentLensSession.start(
        SessionStart(
            original_instruction=(
                "Implement AgentLens safely and ask for approval before risky actions."
            ),
            repo_path=str(PROJECT_ROOT),
        )
    )
    gates = [session.propose(proposal) for proposal in default_demo_proposals(session.session.id)]
    return DemoSessionResponse(session=session.session, gates=gates, timeline=session.timeline())


@app.post("/sessions/{session_id}/tool-calls")
def propose_tool_call(session_id: str, payload: ToolCallProposal) -> Gate:
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="session not found")
    if payload.session_id != session_id:
        raise HTTPException(status_code=400, detail="payload session_id does not match path")
    session = AgentLensSession(store.get_session(session_id))
    return session.propose(payload)


@app.get("/sessions/{session_id}/timeline")
def timeline(session_id: str) -> Timeline:
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="session not found")
    session = AgentLensSession(store.get_session(session_id))
    return session.timeline()


@app.get("/gates/pending")
def pending_gates() -> list[Gate]:
    return store.pending_gates()


@app.post("/gates/{gate_id}/approve")
def approve_gate(gate_id: str, payload: DecisionPayload) -> Gate:
    return _resolve_gate(gate_id, GateStatus.APPROVED, payload)


@app.post("/gates/{gate_id}/block")
def block_gate(gate_id: str, payload: DecisionPayload) -> Gate:
    return _resolve_gate(gate_id, GateStatus.BLOCKED, payload)


@app.post("/gates/{gate_id}/modify")
def modify_gate(gate_id: str, payload: DecisionPayload) -> Gate:
    return _resolve_gate(gate_id, GateStatus.MODIFIED, payload)


@app.post("/gates/{gate_id}/explain")
def explain_gate(gate_id: str) -> dict[str, object]:
    gate = store.gates.get(gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail="gate not found")
    return {
        "gate_id": gate.id,
        "summary": gate.intelligence_card.summary if gate.intelligence_card else None,
        "risk": gate.risk_assessment,
        "policy": gate.policy_decision,
    }


def _resolve_gate(gate_id: str, status: GateStatus, payload: DecisionPayload) -> Gate:
    gate = store.gates.get(gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail="gate not found")
    if gate.status != GateStatus.PENDING:
        return gate
    gate.status = status
    gate.human_reason = payload.reason
    gate.modified_instruction = payload.modified_instruction
    gate.resolved_at = datetime.now(UTC)
    return store.update_gate(gate)
