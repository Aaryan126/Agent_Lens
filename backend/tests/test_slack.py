from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from agentlens.api import app
from agentlens.schemas import GateStatus, SessionStart, ToolCallProposal
from agentlens.session import AgentLensSession
from agentlens.slack import render_gate_message, verify_slack_signature
from agentlens.storage import InMemoryStore, store


def test_slack_signature_verification_accepts_valid_request() -> None:
    secret = "test-secret"
    timestamp = str(int(time.time()))
    body = b"payload=%7B%7D"
    signature = _signature(secret, timestamp, body)

    assert verify_slack_signature(
        signing_secret=secret,
        timestamp=timestamp,
        signature=signature,
        body=body,
    )


def test_slack_signature_verification_rejects_stale_request() -> None:
    secret = "test-secret"
    timestamp = str(int(time.time()) - 1000)
    body = b"payload=%7B%7D"
    signature = _signature(secret, timestamp, body)

    assert not verify_slack_signature(
        signing_secret=secret,
        timestamp=timestamp,
        signature=signature,
        body=body,
        now=int(time.time()),
    )


def test_slack_gate_message_contains_decision_buttons(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    gate = _pending_gate(tmp_path)

    message = render_gate_message(gate)

    assert message["replace_original"] is True
    actions_block = message["blocks"][-1]
    assert actions_block["type"] == "actions"
    assert {item["action_id"] for item in actions_block["elements"]} == {
        "approve_gate",
        "block_gate",
        "modify_gate",
        "explain_gate",
    }


def test_slack_action_endpoint_approves_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
    store.clear()
    gate = _pending_gate(tmp_path, storage=store)
    payload = {
        "type": "block_actions",
        "user": {"id": "U123"},
        "actions": [{"action_id": "approve_gate", "value": gate.id}],
    }
    body = urlencode({"payload": json.dumps(payload)}).encode()
    timestamp = str(int(time.time()))

    client = TestClient(app)
    response = client.post(
        "/integrations/slack/actions",
        content=body,
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "x-slack-request-timestamp": timestamp,
            "x-slack-signature": _signature("test-secret", timestamp, body),
        },
    )

    assert response.status_code == 200
    assert store.gates[gate.id].status == GateStatus.APPROVED
    assert response.json()["replace_original"] is True


def test_slack_action_endpoint_rejects_bad_signature(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
    store.clear()
    gate = _pending_gate(tmp_path, storage=store)
    body = urlencode(
        {
            "payload": json.dumps(
                {
                    "type": "block_actions",
                    "user": {"id": "U123"},
                    "actions": [{"action_id": "approve_gate", "value": gate.id}],
                }
            )
        }
    ).encode()

    client = TestClient(app)
    response = client.post(
        "/integrations/slack/actions",
        content=body,
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "x-slack-request-timestamp": str(int(time.time())),
            "x-slack-signature": "v0=bad",
        },
    )

    assert response.status_code == 401


def _pending_gate(tmp_path: Path, storage: InMemoryStore | None = None):
    active_store = storage or InMemoryStore()
    session = AgentLensSession.start(
        SessionStart(original_instruction="Review writes.", repo_path=str(tmp_path)),
        storage=active_store,
    )
    return session.propose(
        ToolCallProposal(
            session_id=session.session.id,
            tool_name="fs.write",
            params={"path": "notes.md"},
            confidence=0.8,
        )
    )


def _signature(secret: str, timestamp: str, body: bytes) -> str:
    base = f"v0:{timestamp}:{body.decode()}".encode()
    digest = hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"
