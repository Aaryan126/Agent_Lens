from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentlens.schemas import ToolCallProposal

Runner = Callable[[list[str], str | None, int], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class CodexExecResult:
    returncode: int
    stdout: str
    stderr: str
    proposals: list[ToolCallProposal]


class CodexCliAdapter:
    """Adapter for the installed Codex CLI non-interactive JSONL mode."""

    def __init__(self, binary: str = "codex", runner: Runner | None = None) -> None:
        self.binary = binary
        self.runner = runner or self._run

    def run(
        self,
        *,
        prompt: str,
        session_id: str,
        cwd: str,
        model: str | None = None,
        sandbox: str = "read-only",
        timeout_seconds: int = 120,
    ) -> CodexExecResult:
        command = [
            self.binary,
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            sandbox,
            "--cd",
            str(Path(cwd)),
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)

        completed = self.runner(command, cwd, timeout_seconds)
        return CodexExecResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            proposals=parse_codex_jsonl(completed.stdout.splitlines(), session_id=session_id),
        )

    def _run(
        self, command: list[str], cwd: str | None, timeout_seconds: int
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )


def parse_codex_jsonl(lines: Iterable[str], *, session_id: str) -> list[ToolCallProposal]:
    proposals: list[ToolCallProposal] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        proposals.extend(_proposals_from_event(event, session_id=session_id))
    return proposals


def _proposals_from_event(event: dict[str, Any], *, session_id: str) -> list[ToolCallProposal]:
    event_type = str(event.get("type") or event.get("event") or "")
    tool_name = event.get("tool_name") or event.get("tool")
    params = event.get("params") or event.get("arguments") or event.get("input") or {}

    item = event.get("item")
    if isinstance(item, dict) and event_type == "item.started":
        item_type = item.get("type")
        if item_type == "command_execution":
            tool_name = "shell"
            params = {"command": item.get("command"), "status": item.get("status")}
        elif item_type in {"tool_call", "function_call"}:
            tool_name = item.get("name") or item.get("tool_name")
            params = item.get("arguments") or item.get("params") or {}
        elif item_type == "file_change":
            return _file_change_proposals(item, event, session_id=session_id)

    if not tool_name and event_type in {"tool_call", "tool_call.created", "exec_tool_call"}:
        tool_name = event.get("name") or event.get("call", {}).get("name")
        params = event.get("call", {}).get("arguments") or params

    if not tool_name:
        return []

    normalized_tool = _normalize_tool_name(str(tool_name), params)
    if normalized_tool is None:
        return []

    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            params = {"raw": params}
    if not isinstance(params, dict):
        params = {"value": params}

    return [
        ToolCallProposal(
            session_id=session_id,
            tool_name=normalized_tool,
            params=params,
            stated_reason=event.get("reason") or event.get("summary"),
            confidence=event.get("confidence"),
            provider_metadata={"source": "codex_cli", "event_type": event_type, "raw_event": event},
        )
    ]


def _file_change_proposals(
    item: dict[str, Any], event: dict[str, Any], *, session_id: str
) -> list[ToolCallProposal]:
    proposals: list[ToolCallProposal] = []
    for change in item.get("changes") or []:
        if not isinstance(change, dict):
            continue
        kind = str(change.get("kind") or "").lower()
        path = change.get("path")
        if not path:
            continue
        if kind in {"add", "modify", "update"}:
            tool_name = "fs.write"
        elif kind in {"delete", "remove"}:
            tool_name = "fs.delete"
        else:
            tool_name = "fs.write"
        proposals.append(
            ToolCallProposal(
                session_id=session_id,
                tool_name=tool_name,
                params={"path": path, "kind": kind},
                stated_reason=f"Codex file change: {kind or 'unknown'} {path}",
                provider_metadata={
                    "source": "codex_cli",
                    "event_type": str(event.get("type") or ""),
                    "raw_event": event,
                },
            )
        )
    return proposals


def _normalize_tool_name(tool_name: str, params: dict[str, Any] | str | Any) -> str | None:
    lower = tool_name.lower()
    if lower in {"bash", "shell", "exec", "terminal", "command"}:
        return "shell.run"
    if lower in {"read", "fs.read", "file_read", "read_file"}:
        return "fs.read"
    if lower in {"edit", "write", "fs.write", "file_write", "apply_patch"}:
        return "fs.write"
    if lower in {"delete", "fs.delete", "file_delete"}:
        return "fs.delete"
    if lower in {"api", "api.call", "http"}:
        return "api.call"
    if lower in {"db", "db.query", "sql"}:
        return "db.query"
    if lower.startswith("shell") or "exec" in lower:
        return "shell.run"
    if lower.startswith("fs."):
        return lower
    return None
