from __future__ import annotations

import argparse
import base64
import select
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import httpx

from agentlens.adapters.codex_app_server import (
    AppServerApproval,
    CodexAppServerAdapter,
)
from agentlens.schemas import GateStatus, ToolCallProposal

TerminalDecision = tuple[str, str | None]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Codex through AgentLens using Codex app-server approval callbacks."
    )
    parser.add_argument("prompt", nargs="*", help="Optional single Codex task. Omit for a prompt loop.")
    parser.add_argument("--repo", default=".", help="Repository path for Codex and AgentLens.")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8787",
        help="AgentLens API URL. Defaults to the local guard.",
    )
    parser.add_argument(
        "--dashboard-url",
        default="http://localhost:3000",
        help="AgentLens dashboard URL.",
    )
    parser.add_argument("--model", default=None, help="Optional Codex model override.")
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Codex sandbox for app-server turns.",
    )
    parser.add_argument(
        "--approval-policy",
        default="untrusted",
        choices=["untrusted", "on-request", "on-failure", "never"],
        help="Codex approval policy. Use untrusted for the strongest AgentLens gate coverage.",
    )
    parser.add_argument(
        "--approval-timeout",
        type=int,
        default=300,
        help="Seconds to wait for a pending AgentLens dashboard decision.",
    )
    parser.add_argument("--timeout", type=int, default=900, help="Per-turn timeout in seconds.")
    args = parser.parse_args()

    repo = str(Path(args.repo).expanduser().resolve())
    api_url = args.api_url.rstrip("/")
    dashboard_url = args.dashboard_url.rstrip("/")
    prompts = [" ".join(args.prompt).strip()] if args.prompt else []

    if prompts and prompts[0]:
        _run_one(args, prompt=prompts[0], repo=repo, api_url=api_url, dashboard_url=dashboard_url)
        return

    print("AgentLens guarded terminal")
    print(f"Repo:      {repo}")
    print(f"API:       {api_url}")
    print(f"Dashboard: {dashboard_url}")
    print("Type a Codex task, or /exit to quit.\n")
    while True:
        try:
            prompt = input("AgentLens task> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not prompt:
            continue
        if prompt in {"/exit", "/quit", "exit", "quit"}:
            return
        _run_one(args, prompt=prompt, repo=repo, api_url=api_url, dashboard_url=dashboard_url)


def _run_one(
    args: argparse.Namespace,
    *,
    prompt: str,
    repo: str,
    api_url: str,
    dashboard_url: str,
) -> None:
    session_id = _create_session(api_url=api_url, prompt=prompt, repo=repo)
    session_dashboard_url = f"{dashboard_url}?{urlencode({'session': session_id, 'api': api_url})}"
    print(f"\nAgentLens session: {session_id}")
    print(f"Dashboard:         {session_dashboard_url}")
    print("Starting Codex app-server turn...\n")

    bridge = AgentLensApprovalBridge(
        api_url=api_url,
        session_id=session_id,
        dashboard_url=dashboard_url,
        approval_timeout=args.approval_timeout,
    )
    result = CodexAppServerAdapter().run_turn(
        prompt=prompt,
        session_id=session_id,
        cwd=repo,
        model=args.model,
        sandbox=args.sandbox,
        approval_policy=args.approval_policy,
        timeout_seconds=args.timeout,
        approval_handler=bridge.handle,
        event_handler=_print_event,
    )
    print(f"\nCodex turn completed: {result.final_status or 'unknown'}")
    print(f"Approval callbacks handled: {len(result.proposals)}\n")


class AgentLensApprovalBridge:
    def __init__(
        self,
        *,
        api_url: str,
        session_id: str,
        approval_timeout: int,
        dashboard_url: str | None = None,
        terminal_decision_reader: Callable[[], TerminalDecision | None] | None = None,
    ) -> None:
        self.api_url = api_url
        self.session_id = session_id
        self.dashboard_url = dashboard_url.rstrip("/") if dashboard_url else None
        self.approval_timeout = approval_timeout
        self.terminal_decision_reader = terminal_decision_reader or self._read_terminal_decision

    def handle(self, proposal: ToolCallProposal, request: dict[str, Any]) -> AppServerApproval:
        gate = self._post_proposal(proposal)
        status = str(gate.get("status") or "")
        gate_id = str(gate.get("id") or "")
        summary = ((gate.get("intelligence_card") or {}).get("summary")) or ""

        if status in {"auto_executed", "approved", "modified"}:
            print(f"\nAgentLens allowed {proposal.tool_name}: {status}")
            return AppServerApproval(decision=GateStatus.AUTO_EXECUTED, gate_id=gate_id, summary=summary)
        if status == "blocked":
            print(f"\nAgentLens blocked {proposal.tool_name}: {summary}")
            return AppServerApproval(decision=GateStatus.BLOCKED, gate_id=gate_id, summary=summary)
        if status != "pending" or not gate_id:
            print(f"\nAgentLens could not resolve {proposal.tool_name}; cancelling safely.")
            return AppServerApproval(decision=GateStatus.BLOCKED, gate_id=gate_id, summary=summary)

        print(f"\nAgentLens approval required: {proposal.tool_name} ({gate_id})")
        if self.dashboard_url:
            gate_url = f"{self.dashboard_url}?{urlencode({'session': self.session_id, 'api': self.api_url, 'gate': gate_id})}"
            print(f"Review gate: {gate_url}")
        print(summary or "Review the pending gate in the dashboard.")
        print("Decision: [a]pprove / [b]lock / [m]odify, or approve in the dashboard.")
        resolved = self._wait_for_decision(gate_id)
        resolved_status = str(resolved.get("status") or "")
        resolved_summary = ((resolved.get("intelligence_card") or {}).get("summary")) or summary
        if resolved_status in {"approved", "modified", "auto_executed"}:
            print(f"AgentLens decision: {resolved_status}")
            return AppServerApproval(
                decision=GateStatus.APPROVED,
                gate_id=gate_id,
                summary=resolved_summary,
            )
        print(f"AgentLens decision: {resolved_status or 'timeout'}; cancelling Codex action.")
        return AppServerApproval(decision=GateStatus.BLOCKED, gate_id=gate_id, summary=resolved_summary)

    def _post_proposal(self, proposal: ToolCallProposal) -> dict[str, Any]:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{self.api_url}/sessions/{self.session_id}/tool-calls",
                json=proposal.model_dump(mode="json"),
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}

    def _wait_for_decision(self, gate_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.approval_timeout
        latest: dict[str, Any] = {"id": gate_id, "status": "pending"}
        with httpx.Client(timeout=10) as client:
            while time.monotonic() < deadline:
                terminal_decision = self.terminal_decision_reader()
                if terminal_decision:
                    return self._submit_terminal_decision(client, gate_id, terminal_decision)
                response = client.get(f"{self.api_url}/gates/{gate_id}")
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    latest = data
                    if str(data.get("status") or "") != "pending":
                        return data
        return latest

    def _submit_terminal_decision(
        self,
        client: httpx.Client,
        gate_id: str,
        terminal_decision: TerminalDecision,
    ) -> dict[str, Any]:
        action, modified_instruction = terminal_decision
        payload: dict[str, str] = {"reason": "Reviewed from the AgentLens terminal."}
        if action == "modify":
            payload["modified_instruction"] = (
                modified_instruction
                or "Continue only with the narrowest safe version of the requested change."
            )
        response = client.post(
            f"{self.api_url}/gates/{gate_id}/{action}",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"id": gate_id, "status": action}

    def _read_terminal_decision(self) -> TerminalDecision | None:
        if not sys.stdin.isatty():
            time.sleep(1.0)
            return None
        ready, _, _ = select.select([sys.stdin], [], [], 1.0)
        if not ready:
            return None
        raw = sys.stdin.readline().strip().lower()
        if raw in {"a", "approve", "approved", "y", "yes"}:
            return ("approve", None)
        if raw in {"b", "block", "blocked", "n", "no"}:
            return ("block", None)
        if raw in {"m", "modify", "modified"}:
            print("Modified instruction> ", end="", flush=True)
            modified_instruction = sys.stdin.readline().strip()
            return ("modify", modified_instruction)
        print("Use a/approve, b/block, or m/modify. Waiting for a dashboard or terminal decision.")
        return None


def _create_session(*, api_url: str, prompt: str, repo: str) -> str:
    with httpx.Client(timeout=30) as client:
        response = client.post(
            f"{api_url}/sessions",
            json={"original_instruction": prompt, "repo_path": repo},
        )
        response.raise_for_status()
        return str(response.json()["id"])


def _print_event(message: dict[str, Any]) -> None:
    method = str(message.get("method") or "")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    if method == "item/agentMessage/delta":
        delta = _find_first_string(params, {"delta", "text"})
        if delta:
            print(delta, end="", flush=True)
    elif method == "item/started":
        item = params.get("item") if isinstance(params.get("item"), dict) else {}
        readable = _item_label(item)
        if readable:
            print(f"\n{readable}")
    elif method in {"item/commandExecution/outputDelta", "command/exec/outputDelta"}:
        chunk = _find_first_string(params, {"chunk", "data", "delta"})
        if chunk:
            print(_decode_chunk(chunk), end="", flush=True)
    elif method == "turn/completed":
        status = _find_first_string(params, {"status"})
        if status:
            print(f"\nTurn status: {status}")


def _item_label(item: dict[str, Any]) -> str | None:
    item_type = item.get("type")
    if isinstance(item_type, dict):
        item_type = next(iter(item_type.keys()), None)
    if item_type == "commandExecution":
        command = _find_first_string(item, {"command"})
        return f"$ {command}" if command else "$ command execution"
    if item_type == "fileChange":
        return "File change proposed"
    return None


def _decode_chunk(value: str) -> str:
    try:
        decoded = base64.b64decode(value).decode("utf-8", errors="replace")
    except Exception:
        return value
    return decoded


def _find_first_string(value: Any, keys: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and isinstance(item, str) and item:
                return item
        for item in value.values():
            found = _find_first_string(item, keys)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_first_string(item, keys)
            if found:
                return found
    return None


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
