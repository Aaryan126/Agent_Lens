from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from agentlens.adapters.codex_cli import _normalize_tool_name
from agentlens.schemas import ToolCallProposal


def main() -> None:
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
    proposal = _proposal_from_hook(payload, event_name=args.event, session_id=session_id)
    if proposal is None:
        return
    signature = _proposal_signature(proposal)
    if _is_duplicate(session_file, signature):
        return

    try:
        _post_proposal(api_url=api_url, session_id=session_id, proposal=proposal)
        _remember_signature(session_file, signature)
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
            _post_proposal(api_url=api_url, session_id=session_id, proposal=proposal)
            _remember_signature(session_file, _proposal_signature(proposal))
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

    state = {"session_id": session_id, "api_url": api_url, "recent_proposals": []}
    if not reset_recent:
        state["recent_proposals"] = _load_session_state(session_file).get("recent_proposals", [])[-20:]
    _write_session_state(session_file, state)
    return session_id


def _post_proposal(*, api_url: str, session_id: str, proposal: ToolCallProposal) -> None:
    with httpx.Client(timeout=10) as client:
        client.post(
            f"{api_url}/sessions/{session_id}/tool-calls",
            json=proposal.model_dump(mode="json"),
        ).raise_for_status()


def _proposal_signature(proposal: ToolCallProposal) -> str:
    payload = {
        "tool_name": proposal.tool_name,
        "params": proposal.params,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _is_duplicate(session_file: Path, signature: str) -> bool:
    recent = _load_session_state(session_file).get("recent_proposals", [])
    return signature in recent


def _remember_signature(session_file: Path, signature: str) -> None:
    state = _load_session_state(session_file)
    recent = [item for item in state.get("recent_proposals", []) if isinstance(item, str)]
    if signature not in recent:
        recent.append(signature)
    state["recent_proposals"] = recent[-30:]
    _write_session_state(session_file, state)


def _proposal_from_hook(
    payload: dict[str, Any], *, event_name: str, session_id: str
) -> ToolCallProposal | None:
    tool_name = _extract_tool_name(payload, event_name)
    params = _extract_params(payload)
    normalized = _normalize_tool_name(tool_name, params)
    if normalized is None:
        return None

    return ToolCallProposal(
        session_id=session_id,
        tool_name=normalized,
        params=params,
        stated_reason=f"Codex {event_name} hook observed {tool_name}.",
        provider_metadata={
            "source": "codex_hook",
            "hook_event": event_name,
            "raw_event": payload,
        },
    )


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
