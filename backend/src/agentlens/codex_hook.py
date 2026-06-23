from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from agentlens.adapters.codex_cli import _normalize_tool_name
from agentlens.schemas import GateStatus, ToolCallProposal


def main() -> None:
    if os.environ.get("AGENTLENS_DISABLE_HOOKS", "").lower() in {"1", "true", "yes"}:
        return

    parser = argparse.ArgumentParser(
        description="Mirror Codex hook events from an interactive TUI session into AgentLens."
    )
    parser.add_argument("event", nargs="?", default="Unknown", help="Codex hook event name.")
    parser.add_argument(
        "--api-url",
        default=os.environ.get("AGENTLENS_API_URL", "http://127.0.0.1:8787"),
        help="AgentLens API URL. Defaults to the local guard.",
    )
    parser.add_argument(
        "--session-file",
        default=os.environ.get("AGENTLENS_SESSION_FILE", ".agentlens/codex_hook_session.json"),
        help="Local file used to remember the AgentLens session for this repo.",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("AGENTLENS_REPO", "."),
        help="Repository path associated with the Codex session.",
    )
    parser.add_argument(
        "--approval-timeout",
        type=float,
        default=float(os.environ.get("AGENTLENS_APPROVAL_TIMEOUT_SECONDS", "25")),
        help="Seconds to wait for pending AgentLens approval decisions.",
    )
    parser.add_argument(
        "--no-enforce",
        action="store_true",
        default=os.environ.get("AGENTLENS_ENFORCE_APPROVALS", "1").lower()
        in {"0", "false", "no"},
        help="Mirror events without failing the hook for blocked or timed-out gates.",
    )
    args = parser.parse_args()

    raw = sys.stdin.read()
    payload = _load_payload(raw)
    api_url = args.api_url.rstrip("/")
    repo = str(Path(args.repo).expanduser().resolve())
    session_file = Path(args.session_file)

    if args.event == "UserPromptSubmit":
        _create_session(
            api_url=api_url,
            session_file=session_file,
            repo=repo,
            payload=payload,
            event_name=args.event,
            reset_recent=True,
        )
        return

    session_id = os.environ.get("AGENTLENS_SESSION_ID") or _load_session_id(session_file)
    if session_id is None:
        session_id = _create_session(
            api_url=api_url,
            session_file=session_file,
            repo=repo,
            payload=payload,
            event_name=args.event,
        )
    state = _load_session_state(session_file)
    latest_prompt = state.get("latest_prompt") or "Interactive Codex TUI session"
    proposal = _proposal_from_hook(
        payload, event_name=args.event, session_id=session_id, latest_prompt=latest_prompt
    )
    if proposal is None:
        return
    signature = _proposal_signature(proposal)
    existing_gate = _gate_for_signature(session_file, signature)
    if existing_gate:
        _enforce_gate(
            api_url=api_url,
            gate=existing_gate,
            approval_timeout=args.approval_timeout,
            enforce=not args.no_enforce,
        )
        return

    try:
        gate = _post_proposal(api_url=api_url, session_id=session_id, proposal=proposal)
        _remember_gate(session_file, signature, gate)
        _enforce_gate(
            api_url=api_url,
            gate=gate,
            approval_timeout=args.approval_timeout,
            enforce=not args.no_enforce,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404 or os.environ.get("AGENTLENS_SESSION_ID"):
            print(f"AgentLens hook mirror failed: {exc}", file=sys.stderr)
            return
        try:
            session_id = _create_session(
                api_url=api_url,
                session_file=session_file,
                repo=repo,
                payload=payload,
                event_name=args.event,
            )
            proposal.session_id = session_id
            gate = _post_proposal(api_url=api_url, session_id=session_id, proposal=proposal)
            _remember_gate(session_file, _proposal_signature(proposal), gate)
            _enforce_gate(
                api_url=api_url,
                gate=gate,
                approval_timeout=args.approval_timeout,
                enforce=not args.no_enforce,
            )
        except Exception as retry_exc:
            print(f"AgentLens hook mirror retry failed: {retry_exc}", file=sys.stderr)
    except Exception as exc:
        print(f"AgentLens hook mirror failed: {exc}", file=sys.stderr)


def _load_payload(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return payload if isinstance(payload, dict) else {"value": payload}


def _load_session_id(session_file: Path) -> str | None:
    try:
        stored = json.loads(session_file.read_text(encoding="utf-8"))
        session_id = stored.get("session_id")
        if isinstance(session_id, str) and session_id:
            return session_id
    except Exception:
        return None
    return None


def _load_session_state(session_file: Path) -> dict[str, Any]:
    try:
        stored = json.loads(session_file.read_text(encoding="utf-8"))
        return stored if isinstance(stored, dict) else {}
    except Exception:
        return {}


def _write_session_state(session_file: Path, state: dict[str, Any]) -> None:
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _create_session(
    *,
    api_url: str,
    session_file: Path,
    repo: str,
    payload: dict[str, Any],
    event_name: str,
    reset_recent: bool = False,
) -> str:
    session_file = Path(session_file)
    original_instruction = _find_first_string(
        payload,
        {"prompt", "user_prompt", "instruction", "input", "message", "text"},
    )
    if not original_instruction:
        original_instruction = f"Interactive Codex TUI session observed through {event_name} hook."

    with httpx.Client(timeout=10) as client:
        response = client.post(
            f"{api_url}/sessions",
            json={"original_instruction": original_instruction, "repo_path": repo},
        )
        response.raise_for_status()
        session_id = str(response.json()["id"])

    state = {
        "session_id": session_id,
        "api_url": api_url,
        "recent_proposals": [],
        "latest_prompt": original_instruction,
    }
    if not reset_recent:
        state["recent_proposals"] = _load_session_state(session_file).get("recent_proposals", [])[-20:]
        state["latest_prompt"] = _load_session_state(session_file).get("latest_prompt") or original_instruction
    _write_session_state(session_file, state)
    return session_id


def _post_proposal(*, api_url: str, session_id: str, proposal: ToolCallProposal) -> dict[str, Any]:
    with httpx.Client(timeout=10) as client:
        response = client.post(
            f"{api_url}/sessions/{session_id}/tool-calls",
            json=proposal.model_dump(mode="json"),
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}


def _fetch_gate(*, api_url: str, gate_id: str) -> dict[str, Any] | None:
    with httpx.Client(timeout=5) as client:
        response = client.get(f"{api_url}/gates/{gate_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None


def _proposal_signature(proposal: ToolCallProposal) -> str:
    payload = {
        "tool_name": proposal.tool_name,
        "params": proposal.params,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _gate_for_signature(session_file: Path, signature: str) -> dict[str, Any] | None:
    state = _load_session_state(session_file)
    gates = state.get("proposal_gates")
    if isinstance(gates, dict):
        gate = gates.get(signature)
        if isinstance(gate, dict):
            return gate
    recent = state.get("recent_proposals", [])
    if signature in recent:
        return {"status": GateStatus.AUTO_EXECUTED, "id": None}
    return None


def _remember_gate(session_file: Path, signature: str, gate: dict[str, Any]) -> None:
    state = _load_session_state(session_file)
    recent = [item for item in state.get("recent_proposals", []) if isinstance(item, str)]
    if signature not in recent:
        recent.append(signature)
    state["recent_proposals"] = recent[-30:]
    proposal_gates = state.get("proposal_gates")
    if not isinstance(proposal_gates, dict):
        proposal_gates = {}
    proposal_gates[signature] = {
        "id": gate.get("id"),
        "status": gate.get("status"),
        "summary": ((gate.get("intelligence_card") or {}).get("summary")),
    }
    state["proposal_gates"] = dict(list(proposal_gates.items())[-30:])
    _write_session_state(session_file, state)


def _enforce_gate(
    *,
    api_url: str,
    gate: dict[str, Any],
    approval_timeout: float,
    enforce: bool,
) -> None:
    if not enforce:
        return
    gate_id = gate.get("id")
    status = gate.get("status")
    if status == GateStatus.AUTO_EXECUTED or status in {"auto_executed", "approved", "modified"}:
        return
    if status == GateStatus.BLOCKED or status == "blocked":
        _deny(gate, "AgentLens blocked this action.")
    if status != GateStatus.PENDING and status != "pending":
        return
    if not gate_id:
        _deny(gate, "AgentLens requires approval but no gate id was returned.")

    deadline = time.monotonic() + max(0.0, approval_timeout)
    latest = gate
    while time.monotonic() < deadline:
        time.sleep(0.75)
        fetched = _fetch_gate(api_url=api_url, gate_id=str(gate_id))
        if fetched is None:
            continue
        latest = fetched
        latest_status = fetched.get("status")
        if latest_status in {"approved", "modified", "auto_executed"}:
            return
        if latest_status == "blocked":
            _deny(fetched, "AgentLens blocked this action.")

    _deny(latest, "AgentLens approval timed out before this action was approved.")


def _deny(gate: dict[str, Any], message: str) -> None:
    card = gate.get("intelligence_card") if isinstance(gate.get("intelligence_card"), dict) else {}
    summary = card.get("summary") or message
    print(f"{message} {summary}", file=sys.stderr)
    raise SystemExit(2)


def _proposal_from_hook(
    payload: dict[str, Any], *, event_name: str, session_id: str, latest_prompt: str
) -> ToolCallProposal | None:
    tool_name = _extract_tool_name(payload, event_name)
    params = _extract_params(payload)
    normalized = _normalize_tool_name(tool_name, params)
    if normalized is None:
        return None

    proposal = ToolCallProposal(
        session_id=session_id,
        tool_name=normalized,
        params=params,
        stated_reason=f"Codex {event_name} hook observed {tool_name}.",
        provider_metadata={
            "source": "codex_hook",
            "hook_event": event_name,
            "raw_event": payload,
            "fast_intelligence": True,
        },
    )
    proposal.params["agentlens_prompt"] = latest_prompt
    return proposal


def _extract_tool_name(payload: dict[str, Any], event_name: str) -> str:
    for key in ("tool_name", "toolName", "tool", "name", "matcher"):
        value = _find_first_string(payload, {key})
        if value:
            return value
    if _find_first_string(payload, {"command", "cmd", "shell_command"}):
        return "Bash"
    return event_name


def _extract_params(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("params", "arguments", "input", "tool_input", "toolInput"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value

    params: dict[str, Any] = {"hook_payload": payload}
    command = _find_first_string(payload, {"command", "cmd", "shell_command"})
    if command:
        params["command"] = command
    path = _find_first_string(payload, {"path", "file_path", "filePath"})
    if path:
        params["path"] = path
    return params


def _find_first_string(value: Any, keys: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and isinstance(item, str) and item.strip():
                return item.strip()
        for item in value.values():
            found = _find_first_string(item, keys)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first_string(item, keys)
            if found:
                return found
    return None


if __name__ == "__main__":
    main()
