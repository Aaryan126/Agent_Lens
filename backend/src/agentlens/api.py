from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentlens.analytics import build_ledger_analytics
from agentlens.adapters.codex_cli import CodexCliAdapter
from agentlens.config import load_settings
from agentlens.schemas import (
    Gate,
    GateStatus,
    ExplainMoreResponse,
    LedgerAnalytics,
    Session,
    SessionStart,
    Timeline,
    ToolCallProposal,
)
from agentlens.session import AgentLensSession
from agentlens.simulator import default_demo_proposals
from agentlens.slack import (
    decode_slack_payload,
    parse_slack_action,
    post_gate_message,
    render_explain_message,
    render_gate_message,
    require_valid_slack_request,
    update_gate_message,
)
from agentlens.storage import store

app = FastAPI(title="AgentLens", version="0.1.0")
settings = load_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(os.environ.get("AGENTLENS_PROJECT_ROOT", Path(__file__).resolve().parents[3]))


class DecisionPayload(BaseModel):
    reason: str | None = None
    modified_instruction: str | None = None


class DemoSessionResponse(BaseModel):
    session: Session
    gates: list[Gate]
    timeline: Timeline


class SlackDemoPayload(BaseModel):
    channel_id: str | None = None


class CodexRunPayload(BaseModel):
    prompt: str
    repo_path: str | None = None
    model: str | None = None
    sandbox: str = "read-only"
    timeout_seconds: int = 120


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sessions")
def create_session(payload: SessionStart):
    session = AgentLensSession.start(payload)
    return session.session


@app.get("/sessions")
def list_sessions(limit: int = 20) -> list[Session]:
    sessions = sorted(store.sessions.values(), key=lambda session: session.created_at, reverse=True)
    return sessions[: max(1, min(limit, 100))]


@app.get("/sessions/latest")
def latest_session() -> Session:
    if not store.sessions:
        raise HTTPException(status_code=404, detail="no sessions found")
    return max(store.sessions.values(), key=lambda session: session.created_at)


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


@app.post("/demo/slack/send")
def send_demo_slack_cards(payload: SlackDemoPayload) -> dict[str, object]:
    settings = load_settings()
    channel_id = payload.channel_id or settings.slack_channel_id
    demo = create_demo_session()
    posted = []
    for gate in demo.gates:
        if gate.status == GateStatus.PENDING:
            result = post_gate_message(
                bot_token=settings.slack_bot_token,
                channel_id=channel_id,
                gate=gate,
            )
            posted.append({"gate_id": gate.id, "channel": result.get("channel"), "ts": result.get("ts")})
    return {"session_id": demo.session.id, "posted": posted}


@app.post("/codex/sessions")
def run_codex_session(payload: CodexRunPayload) -> DemoSessionResponse:
    repo_path = str(Path(payload.repo_path or PROJECT_ROOT))
    session = AgentLensSession.start(
        SessionStart(
            original_instruction=payload.prompt,
            repo_path=repo_path,
        )
    )
    result = CodexCliAdapter().run(
        prompt=payload.prompt,
        session_id=session.session.id,
        cwd=repo_path,
        model=payload.model,
        sandbox=payload.sandbox,
        timeout_seconds=payload.timeout_seconds,
    )
    if result.returncode != 0 and not result.proposals:
        raise HTTPException(
            status_code=502,
            detail=result.stderr or "Codex CLI failed before emitting tool-call proposals",
        )
    gates = [session.propose(proposal) for proposal in result.proposals]
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


@app.get("/sessions/{session_id}/analytics")
def session_analytics(session_id: str) -> LedgerAnalytics:
    if session_id not in store.sessions:
        raise HTTPException(status_code=404, detail="session not found")
    _, gates = store.timeline(session_id)
    return build_ledger_analytics(session_id, gates)


@app.get("/gates/pending")
def pending_gates() -> list[Gate]:
    return store.pending_gates()


@app.get("/gates/{gate_id}")
def get_gate(gate_id: str) -> Gate:
    gate = store.gates.get(gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail="gate not found")
    return gate


@app.get("/audit/events")
def audit_events(limit: int = 100) -> dict[str, object]:
    events = store.audit_log.read_all()
    return {"events": events[-limit:]}


@app.post("/gates/{gate_id}/approve")
def approve_gate(gate_id: str, payload: DecisionPayload) -> Gate:
    return _resolve_gate(gate_id, GateStatus.APPROVED, payload)


@app.post("/gates/{gate_id}/block")
def block_gate(gate_id: str, payload: DecisionPayload) -> Gate:
    return _resolve_gate(gate_id, GateStatus.BLOCKED, payload)


@app.post("/gates/{gate_id}/modify")
def modify_gate(gate_id: str, payload: DecisionPayload) -> Gate:
    return _resolve_gate(gate_id, GateStatus.MODIFIED, payload)


@app.post("/gates/{gate_id}/observe")
def observe_gate(gate_id: str, payload: DecisionPayload) -> Gate:
    return _resolve_gate(gate_id, GateStatus.AUTO_EXECUTED, payload)


@app.post("/gates/{gate_id}/explain")
def explain_gate(gate_id: str) -> ExplainMoreResponse:
    gate = store.gates.get(gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail="gate not found")
    session = AgentLensSession(store.get_session(gate.session_id))
    try:
        return session.explain(gate_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="gate not found") from None


@app.post("/integrations/slack/actions")
async def slack_actions(request: Request) -> dict[str, object]:
    body = await request.body()
    require_valid_slack_request(load_settings(), dict(request.headers), body)

    form = parse_qs(body.decode())
    raw_payload = (form.get("payload") or [None])[0]
    if raw_payload is None:
        raise HTTPException(status_code=400, detail="Slack request missing payload")

    payload = decode_slack_payload(raw_payload)
    action = parse_slack_action(payload)
    gate = store.gates.get(action.gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail="gate not found")

    if action.action == "explain_gate":
        return render_explain_message(gate)
    if action.action == "approve_gate":
        gate = _resolve_gate(
            action.gate_id,
            GateStatus.APPROVED,
            DecisionPayload(reason=f"Approved in Slack by {action.user_id or 'unknown user'}."),
        )
    elif action.action == "block_gate":
        gate = _resolve_gate(
            action.gate_id,
            GateStatus.BLOCKED,
            DecisionPayload(reason=f"Blocked in Slack by {action.user_id or 'unknown user'}."),
        )
    elif action.action == "modify_gate":
        gate = _resolve_gate(
            action.gate_id,
            GateStatus.MODIFIED,
            DecisionPayload(
                reason=f"Modified in Slack by {action.user_id or 'unknown user'}.",
                modified_instruction=(
                    "Continue only after inspecting references and proposing a safer scoped change."
                ),
            ),
        )
    if action.channel_id and action.message_ts:
        update_gate_message(
            bot_token=load_settings().slack_bot_token,
            channel_id=action.channel_id,
            message_ts=action.message_ts,
            gate=gate,
        )
    return render_gate_message(gate)


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
