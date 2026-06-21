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
from agentlens.slack import (
    parse_slack_action,
    post_gate_message,
    render_gate_message,
    update_gate_message,
    verify_slack_signature,
)
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
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    store.clear()
    gate = _pending_gate(tmp_path, storage=store)
    updates = []

    def fake_update_gate_message(*, bot_token, channel_id, message_ts, gate):
        updates.append(
            {
                "bot_token": bot_token,
                "channel_id": channel_id,
                "message_ts": message_ts,
                "gate_id": gate.id,
            }
        )
        return {"ok": True}

    monkeypatch.setattr("agentlens.api.update_gate_message", fake_update_gate_message)
    payload = {
        "type": "block_actions",
        "user": {"id": "U123"},
        "channel": {"id": "C123"},
        "message": {"ts": "123.456"},
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
    assert updates == [
        {
            "bot_token": "xoxb-test",
            "channel_id": "C123",
            "message_ts": "123.456",
            "gate_id": gate.id,
        }
    ]


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


def test_demo_slack_send_endpoint_posts_backend_owned_gates(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    store.clear()
    posted = []

    def fake_post_gate_message(*, bot_token, channel_id, gate):
        posted.append({"bot_token": bot_token, "channel_id": channel_id, "gate_id": gate.id})
        return {"ok": True, "channel": channel_id, "ts": f"ts-{len(posted)}"}

    monkeypatch.setattr("agentlens.api.post_gate_message", fake_post_gate_message)

    client = TestClient(app)
    response = client.post("/demo/slack/send", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"].startswith("ses_")
    assert len(body["posted"]) == 2
    assert len(posted) == 2
    assert all(item["gate_id"] in store.gates for item in posted)


def test_post_gate_message_sends_block_kit_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    gate = _pending_gate(tmp_path)
    client = FakeSlackHttpClient({"ok": True, "channel": "C123", "ts": "123.456"})

    result = post_gate_message(
        bot_token="xoxb-test",
        channel_id="C123",
        gate=gate,
        http_client=client,
    )

    assert result["ok"] is True
    assert client.requests[0]["url"] == "https://slack.com/api/chat.postMessage"
    assert client.requests[0]["json"]["channel"] == "C123"
    assert client.requests[0]["json"]["blocks"][-1]["type"] == "actions"


def test_update_gate_message_removes_decision_buttons_after_resolution(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    gate = _pending_gate(tmp_path)
    gate.status = GateStatus.APPROVED
    client = FakeSlackHttpClient({"ok": True, "channel": "C123", "ts": "123.456"})

    result = update_gate_message(
        bot_token="xoxb-test",
        channel_id="C123",
        message_ts="123.456",
        gate=gate,
        http_client=client,
    )

    assert result["ok"] is True
    assert client.requests[0]["url"] == "https://slack.com/api/chat.update"
    assert client.requests[0]["json"]["channel"] == "C123"
    assert client.requests[0]["json"]["ts"] == "123.456"
    assert client.requests[0]["json"]["blocks"][-1]["type"] != "actions"


def test_post_gate_message_surfaces_slack_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "replace_me")
    gate = _pending_gate(tmp_path)
    client = FakeSlackHttpClient({"ok": False, "error": "channel_not_found"})

    try:
        post_gate_message(
            bot_token="xoxb-test",
            channel_id="C404",
            gate=gate,
            http_client=client,
        )
    except RuntimeError as exc:
        assert "channel_not_found" in str(exc)
    else:
        raise AssertionError("expected Slack API error")


def test_parse_slack_action_extracts_message_target() -> None:
    action = parse_slack_action(
        {
            "user": {"id": "U123"},
            "channel": {"id": "C123"},
            "message": {"ts": "123.456"},
            "actions": [{"action_id": "approve_gate", "value": "gate_123"}],
        }
    )

    assert action.user_id == "U123"
    assert action.channel_id == "C123"
    assert action.message_ts == "123.456"


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


class FakeSlackResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSlackHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def post(self, url, headers, json):
        self.requests.append({"url": url, "headers": headers, "json": json})
        return FakeSlackResponse(self.payload)
