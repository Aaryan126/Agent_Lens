from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException

from agentlens.config import Settings
from agentlens.schemas import Gate, GateStatus

SLACK_VERSION = "v0"
SIGNATURE_TOLERANCE_SECONDS = 60 * 5


@dataclass(frozen=True)
class SlackAction:
    action: str
    gate_id: str
    user_id: str | None = None
    channel_id: str | None = None
    message_ts: str | None = None


def verify_slack_signature(
    *,
    signing_secret: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    now: int | None = None,
) -> bool:
    if not signing_secret or signing_secret == "replace_me":
        return False
    if not timestamp or not signature:
        return False

    try:
        request_time = int(timestamp)
    except ValueError:
        return False

    current_time = int(time.time()) if now is None else now
    if abs(current_time - request_time) > SIGNATURE_TOLERANCE_SECONDS:
        return False

    base = f"{SLACK_VERSION}:{timestamp}:{body.decode()}".encode()
    digest = hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    expected = f"{SLACK_VERSION}={digest}"
    return hmac.compare_digest(expected, signature)


def require_valid_slack_request(settings: Settings, headers: dict[str, str], body: bytes) -> None:
    ok = verify_slack_signature(
        signing_secret=settings.slack_signing_secret,
        timestamp=headers.get("x-slack-request-timestamp"),
        signature=headers.get("x-slack-signature"),
        body=body,
    )
    if not ok:
        raise HTTPException(status_code=401, detail="invalid Slack signature")


def render_gate_blocks(gate: Gate) -> list[dict[str, Any]]:
    card = gate.intelligence_card
    risk = card.risk_badge if card else gate.risk_assessment.risk_level
    summary = card.summary if card else "No summary available."
    confidence = round((card.confidence if card else 0.0) * 100)
    trajectory = card.trajectory_preview if card else "No trajectory preview available."
    drift = card.drift_flag if card else None
    status = gate.status.replace("_", " ").upper()

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"AgentLens Gate: {risk.upper()}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Status:* {status}\n*Confidence:* {confidence}%"},
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Trajectory:* {trajectory}"}},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Policy: {gate.policy_decision.matched_policy or 'semantic risk'} | "
                        f"Reversibility: {gate.risk_assessment.reversibility} | "
                        f"Blast radius: {gate.risk_assessment.blast_radius}"
                    ),
                }
            ],
        },
    ]
    if drift:
        blocks.insert(4, {"type": "section", "text": {"type": "mrkdwn", "text": f"*Drift:* {drift}"}})

    if gate.status == GateStatus.PENDING:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    _button("Approve", "approve_gate", gate.id, "primary"),
                    _button("Block", "block_gate", gate.id, "danger"),
                    _button("Modify", "modify_gate", gate.id),
                    _button("Explain more", "explain_gate", gate.id),
                ],
            }
        )
    return blocks


def render_gate_message(gate: Gate, *, response_type: str = "ephemeral") -> dict[str, Any]:
    return {
        "response_type": response_type,
        "replace_original": True,
        "text": gate.intelligence_card.summary if gate.intelligence_card else "AgentLens gate",
        "blocks": render_gate_blocks(gate),
    }


def post_gate_message(
    *,
    bot_token: str,
    channel_id: str,
    gate: Gate,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    if not bot_token or bot_token == "replace_me":
        raise ValueError("SLACK_BOT_TOKEN is required to post Slack messages")
    if not channel_id or channel_id == "replace_me":
        raise ValueError("Slack channel ID is required to post Slack messages")

    message = render_gate_message(gate, response_type="in_channel")
    payload = {
        "channel": channel_id,
        "text": message["text"],
        "blocks": message["blocks"],
    }
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    client = http_client or httpx.Client(timeout=10)
    should_close = http_client is None
    try:
        response = client.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    finally:
        if should_close:
            client.close()

    if not data.get("ok"):
        raise RuntimeError(f"Slack chat.postMessage failed: {data.get('error')}")
    return data


def update_gate_message(
    *,
    bot_token: str,
    channel_id: str,
    message_ts: str,
    gate: Gate,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    if not bot_token or bot_token == "replace_me":
        raise ValueError("SLACK_BOT_TOKEN is required to update Slack messages")
    if not channel_id:
        raise ValueError("Slack channel ID is required to update Slack messages")
    if not message_ts:
        raise ValueError("Slack message timestamp is required to update Slack messages")

    message = render_gate_message(gate, response_type="in_channel")
    payload = {
        "channel": channel_id,
        "ts": message_ts,
        "text": message["text"],
        "blocks": message["blocks"],
    }
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    client = http_client or httpx.Client(timeout=10)
    should_close = http_client is None
    try:
        response = client.post("https://slack.com/api/chat.update", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    finally:
        if should_close:
            client.close()

    if not data.get("ok"):
        raise RuntimeError(f"Slack chat.update failed: {data.get('error')}")
    return data


def render_explain_message(gate: Gate) -> dict[str, Any]:
    card = gate.intelligence_card
    evidence = "\n".join(f"- {item}" for item in gate.risk_assessment.evidence)
    affected = ", ".join(gate.risk_assessment.affected_files) or "No affected files recorded"
    dependency_lines = []
    confidence_lines = []
    if card:
        dependency_lines = [
            f"- {item.path}: {item.summary}"
            for item in card.dependency_evidence[:5]
        ]
        confidence_lines = [
            f"- {item.label}: {item.detail}"
            for item in card.confidence_evidence[:5]
        ]
    trajectory = card.trajectory_preview if card else "No trajectory preview available."
    suggested = "Inspect references, narrow the change, and retry with a reversible action."
    if gate.risk_assessment.risk_level == "critical":
        suggested = "Do not execute this action yet; ask for a reversible migration or rollback plan first."
    return {
        "response_type": "ephemeral",
        "replace_original": False,
        "text": "AgentLens gate explanation",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Why AgentLens gated this action"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Risk:* {gate.risk_assessment.risk_level}\n"
                        f"*Recommended action:* {gate.risk_assessment.recommended_action}\n"
                        f"*Affected files:* {affected}"
                    ),
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Evidence:*\n{evidence}"}},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Trajectory:* {trajectory}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Dependency evidence:*\n"
                    + ("\n".join(dependency_lines) if dependency_lines else "- No dependency references found."),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Confidence factors:*\n"
                    + ("\n".join(confidence_lines) if confidence_lines else "- No confidence factors recorded."),
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Safer next step:* {suggested}"}},
        ],
    }


def parse_slack_action(payload: dict[str, Any]) -> SlackAction:
    actions = payload.get("actions") or []
    if not actions:
        raise HTTPException(status_code=400, detail="Slack payload missing action")
    action = actions[0]
    action_id = action.get("action_id")
    gate_id = action.get("value")
    if action_id not in {"approve_gate", "block_gate", "modify_gate", "explain_gate"}:
        raise HTTPException(status_code=400, detail=f"unsupported Slack action: {action_id}")
    if not gate_id:
        raise HTTPException(status_code=400, detail="Slack payload missing gate id")
    return SlackAction(
        action=action_id,
        gate_id=gate_id,
        user_id=(payload.get("user") or {}).get("id"),
        channel_id=(payload.get("channel") or {}).get("id"),
        message_ts=(payload.get("message") or {}).get("ts"),
    )


def decode_slack_payload(raw_payload: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid Slack payload JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid Slack payload")
    return payload


def _button(text: str, action_id: str, gate_id: str, style: str | None = None) -> dict[str, Any]:
    button: dict[str, Any] = {
        "type": "button",
        "text": {"type": "plain_text", "text": text},
        "action_id": action_id,
        "value": gate_id,
    }
    if style:
        button["style"] = style
    return button
