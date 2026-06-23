from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
import websockets
from websockets.asyncio.server import ServerConnection

from agentlens.adapters.codex_app_server import (
    AppServerApproval,
    approval_response_for_app_server_request,
    proposal_from_app_server_event,
    proposal_from_app_server_request,
)
from agentlens.schemas import GateStatus, SessionStart, ToolCallProposal


APPROVAL_METHODS = {
    "item/commandExecution/requestApproval",
    "item/fileChange/requestApproval",
    "item/permissions/requestApproval",
}
TARGET_HINT_RE = re.compile(r"(?<![\w./-])[\w./-]+\.[A-Za-z0-9_.-]+(?![\w./-])")


@dataclass(frozen=True)
class PendingNativeApproval:
    gate_id: str
    summary: str
    tool_name: str


class AgentLensProxyState:
    def __init__(
        self,
        *,
        api_url: str,
        repo: str,
        dashboard_url: str,
        enrich_native_prompt: bool = True,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.repo = str(Path(repo).expanduser().resolve())
        self.dashboard_url = dashboard_url.rstrip("/")
        self.enrich_native_prompt = enrich_native_prompt
        self.session_id: str | None = None
        self.latest_prompt = "Codex remote TUI session"
        self.pending_native_approvals: dict[int, PendingNativeApproval] = {}
        self.passive_event_signatures: set[str] = set()
        self.recent_target_hints: list[str] = []

    async def observe_client_message(self, message: dict[str, Any]) -> None:
        method = str(message.get("method") or "")
        if method == "thread/start" and self.session_id is not None:
            self.session_id = None
            self.latest_prompt = "Codex remote TUI session"
            self.pending_native_approvals.clear()
            self.passive_event_signatures.clear()
            self.recent_target_hints.clear()
            return
        if method != "turn/start":
            return
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        prompt = _extract_prompt(params) or "Codex remote TUI turn"
        self.latest_prompt = prompt
        self._remember_target_hints(_target_hints_from_text(prompt))
        if self.session_id is None:
            self.session_id = await self._create_session(prompt)
            session_label = "AgentLens session"
        else:
            session_label = "AgentLens session continued"
        dashboard = self.dashboard_url_for_session(self.session_id)
        print(f"{session_label}: {self.session_id}")
        print(f"Dashboard:         {dashboard}")

    async def handle_upstream_message(self, message: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if not _is_approval_request(message):
            await self._mirror_passive_event(message)
            return ("client", message)

        session_id = self.session_id or await self._create_session(self.latest_prompt)
        self.session_id = session_id
        proposal = proposal_from_app_server_request(
            method=str(message.get("method") or ""),
            params=message.get("params") if isinstance(message.get("params"), dict) else {},
            session_id=session_id,
        )
        proposal = self._with_recent_target_hints(proposal)
        proposal.params["agentlens_prompt"] = self.latest_prompt
        gate = await self._post_proposal(proposal)
        status = str(gate.get("status") or "")
        gate_id = str(gate.get("id") or "")
        summary = ((gate.get("intelligence_card") or {}).get("summary")) or ""

        if status in {"auto_executed", "approved", "modified"}:
            approval = AppServerApproval(
                decision=GateStatus.AUTO_EXECUTED,
                gate_id=gate_id,
                summary=summary,
            )
            return ("upstream", approval_response_for_app_server_request(message, approval))

        if status == "blocked":
            approval = AppServerApproval(
                decision=GateStatus.BLOCKED,
                gate_id=gate_id,
                summary=summary,
            )
            return ("upstream", approval_response_for_app_server_request(message, approval))

        request_id = message.get("id")
        if isinstance(request_id, int) and gate_id:
            self.pending_native_approvals[request_id] = PendingNativeApproval(
                gate_id=gate_id,
                summary=summary,
                tool_name=proposal.tool_name,
            )
        return (
            "client",
            self._enrich_approval_message(
                message,
                proposal=proposal,
                gate=gate,
                gate_id=gate_id,
                summary=summary,
            ),
        )

    async def handle_client_message(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("id")
        if isinstance(request_id, int) and request_id in self.pending_native_approvals:
            pending = self.pending_native_approvals.pop(request_id)
            action = "approve" if _client_response_accepts(message) else "block"
            await self._resolve_gate(
                gate_id=pending.gate_id,
                action=action,
                reason=f"Reviewed from native Codex TUI via AgentLens proxy for {pending.tool_name}.",
            )
            stale = list(self.pending_native_approvals.values())
            self.pending_native_approvals.clear()
            for stale_pending in stale:
                await self._resolve_gate(
                    gate_id=stale_pending.gate_id,
                    action=action,
                    reason=(
                        "Resolved with the same native Codex TUI decision because Codex "
                        "continued past an older outstanding AgentLens approval request."
                    ),
                )
        return message

    def dashboard_url_for_session(self, session_id: str) -> str:
        return f"{self.dashboard_url}?{urlencode({'session': session_id, 'api': self.api_url})}"

    def _dashboard_url_for_gate(self, gate_id: str) -> str:
        if not self.session_id:
            return self.dashboard_url
        return f"{self.dashboard_url}?{urlencode({'session': self.session_id, 'api': self.api_url, 'gate': gate_id})}"

    def _enrich_approval_message(
        self,
        message: dict[str, Any],
        *,
        proposal: ToolCallProposal,
        gate: dict[str, Any],
        gate_id: str,
        summary: str,
    ) -> dict[str, Any]:
        if not self.enrich_native_prompt or not summary:
            return message
        enriched = json.loads(json.dumps(message))
        params = enriched.setdefault("params", {})
        if not isinstance(params, dict):
            return message
        dashboard_url = self._dashboard_url_for_gate(gate_id)
        params["reason"] = _native_approval_reason(proposal, gate, repo=self.repo)
        params["agentLens"] = {
            "gateId": gate_id,
            "sessionId": self.session_id,
            "dashboardUrl": dashboard_url,
            "summary": summary,
        }
        return enriched

    async def _create_session(self, prompt: str) -> str:
        payload = SessionStart(original_instruction=prompt, repo_path=self.repo).model_dump(
            mode="json"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.api_url}/sessions", json=payload)
            response.raise_for_status()
            return str(response.json()["id"])

    async def _post_proposal(self, proposal: ToolCallProposal) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_url}/sessions/{proposal.session_id}/tool-calls",
                json=proposal.model_dump(mode="json"),
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}

    async def _mirror_passive_event(self, message: dict[str, Any]) -> None:
        if not self.session_id:
            return
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        proposal = proposal_from_app_server_event(
            method=method,
            params=params,
            session_id=self.session_id,
        )
        if proposal is None:
            return
        proposal.params["agentlens_prompt"] = self.latest_prompt
        self._remember_target_hints(_proposal_target_hints(proposal))
        signature = _passive_event_signature(proposal)
        if signature in self.passive_event_signatures:
            return
        self.passive_event_signatures.add(signature)
        if len(self.passive_event_signatures) > 200:
            self.passive_event_signatures = set(list(self.passive_event_signatures)[-100:])
        try:
            gate = await self._post_proposal(proposal)
            if str(gate.get("status") or "") in {"pending", "blocked"}:
                gate_id = str(gate.get("id") or "")
                if gate_id:
                    await self._mark_passive_observed(gate_id)
        except httpx.HTTPError:
            return

    def _remember_target_hints(self, hints: list[str]) -> None:
        if not hints:
            return
        self.recent_target_hints = _unique_strings([*self.recent_target_hints, *hints])[-12:]

    def _with_recent_target_hints(self, proposal: ToolCallProposal) -> ToolCallProposal:
        if proposal.tool_name not in {"fs.write", "fs.delete"}:
            return proposal
        if _proposal_has_concrete_target(proposal, self.repo):
            self._remember_target_hints(_proposal_target_hints(proposal))
            return proposal
        hints = self.recent_target_hints[-6:]
        if not hints:
            return proposal
        params = dict(proposal.params)
        existing_paths = params.get("paths")
        if isinstance(existing_paths, list):
            paths = [
                str(path)
                for path in existing_paths
                if str(path).strip() and not _is_repo_root_target(str(path), self.repo)
            ]
        else:
            paths = []
        paths = _unique_strings([*hints, *paths])
        if not paths:
            return proposal
        params["paths"] = paths
        params["path"] = paths[0]
        params["target_hints"] = hints
        return proposal.model_copy(update={"params": params})

    async def _resolve_gate(self, *, gate_id: str, action: str, reason: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_url}/gates/{gate_id}/{action}",
                json={"reason": reason},
            )
            response.raise_for_status()

    async def _mark_passive_observed(self, gate_id: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_url}/gates/{gate_id}/observe",
                json={
                    "reason": (
                        "Observed from Codex app-server telemetry after execution; no "
                        "native approval was available for this event."
                    )
                },
            )
            response.raise_for_status()


class CodexAppServerProxy:
    def __init__(
        self,
        *,
        repo: str,
        api_url: str,
        dashboard_url: str,
        proxy_host: str,
        proxy_port: int,
        upstream_host: str,
        upstream_port: int,
        codex_binary: str,
        model: str | None,
        sandbox: str,
        approval_policy: str,
        enrich_native_prompt: bool,
    ) -> None:
        self.repo = str(Path(repo).expanduser().resolve())
        self.api_url = api_url.rstrip("/")
        self.dashboard_url = dashboard_url.rstrip("/")
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.codex_binary = codex_binary
        self.model = model
        self.sandbox = sandbox
        self.approval_policy = approval_policy
        self.enrich_native_prompt = enrich_native_prompt
        self.upstream_process: subprocess.Popen[str] | None = None

    async def run(self) -> None:
        upstream_url = f"ws://{self.upstream_host}:{self.upstream_port}"
        self.upstream_process = self._start_upstream(upstream_url)
        try:
            await self._wait_for_agentlens_api()
            await self._wait_for_upstream()
            print("AgentLens Codex proxy is running.")
            print(f"Repo:      {self.repo}")
            print(f"API:       {self.api_url}")
            print(f"Dashboard: {self.dashboard_url}")
            print(f"Proxy:     ws://{self.proxy_host}:{self.proxy_port}")
            print(f"Upstream:  {upstream_url}")
            print()
            print("Connect Codex TUI with:")
            print(f"  {self._codex_remote_command()}")
            print()
            async with websockets.serve(
                self._handle_client,
                self.proxy_host,
                self.proxy_port,
            ):
                await asyncio.Future()
        finally:
            self._stop_upstream()

    def _start_upstream(self, upstream_url: str) -> subprocess.Popen[str]:
        command = [
            self.codex_binary,
            "app-server",
            "--listen",
            upstream_url,
            "-c",
            f'approval_policy="{self.approval_policy}"',
            "-c",
            f'sandbox_mode="{self.sandbox}"',
        ]
        if self.model:
            command.extend(["-c", f'model="{self.model}"'])
        return subprocess.Popen(
            command,
            cwd=self.repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    async def _wait_for_upstream(self) -> None:
        ready_url = f"http://{self.upstream_host}:{self.upstream_port}/readyz"
        deadline = time.monotonic() + 20
        async with httpx.AsyncClient(timeout=2) as client:
            while time.monotonic() < deadline:
                if self.upstream_process and self.upstream_process.poll() is not None:
                    stderr = self.upstream_process.stderr.read() if self.upstream_process.stderr else ""
                    raise RuntimeError(f"Codex app-server exited before ready: {stderr}")
                try:
                    response = await client.get(ready_url)
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.25)
        raise TimeoutError(f"Timed out waiting for Codex app-server at {ready_url}.")

    async def _wait_for_agentlens_api(self) -> None:
        health_url = f"{self.api_url}/health"
        deadline = time.monotonic() + 10
        async with httpx.AsyncClient(timeout=2) as client:
            while time.monotonic() < deadline:
                try:
                    response = await client.get(health_url)
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.25)
        raise RuntimeError(
            "AgentLens API is not reachable. Start the local guard first:\n"
            f"  cd {Path(self.repo) / 'backend'}\n"
            f"  uv run agentlens-guard --repo {self.repo}\n"
            f"Expected health check: {health_url}"
        )

    async def _handle_client(self, client: ServerConnection) -> None:
        upstream_url = f"ws://{self.upstream_host}:{self.upstream_port}"
        state = AgentLensProxyState(
            api_url=self.api_url,
            repo=self.repo,
            dashboard_url=self.dashboard_url,
            enrich_native_prompt=self.enrich_native_prompt,
        )
        async with websockets.connect(upstream_url) as upstream:
            to_upstream = asyncio.create_task(self._client_to_upstream(client, upstream, state))
            to_client = asyncio.create_task(self._upstream_to_client(upstream, client, state))
            done, pending = await asyncio.wait(
                {to_upstream, to_client},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()

    async def _client_to_upstream(
        self,
        client: ServerConnection,
        upstream: Any,
        state: AgentLensProxyState,
    ) -> None:
        async for raw in client:
            message = _decode_json(raw)
            if message is None:
                await upstream.send(raw)
                continue
            await state.observe_client_message(message)
            outbound = await state.handle_client_message(message)
            outbound = self._with_proxy_policy(outbound)
            await upstream.send(json.dumps(outbound))

    async def _upstream_to_client(
        self,
        upstream: Any,
        client: ServerConnection,
        state: AgentLensProxyState,
    ) -> None:
        async for raw in upstream:
            message = _decode_json(raw)
            if message is None:
                await client.send(raw)
                continue
            target, outbound = await state.handle_upstream_message(message)
            if target == "upstream":
                await upstream.send(json.dumps(outbound))
            else:
                await client.send(json.dumps(outbound))

    def _stop_upstream(self) -> None:
        if self.upstream_process is None or self.upstream_process.poll() is not None:
            return
        self.upstream_process.terminate()
        try:
            self.upstream_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.upstream_process.kill()

    def _with_proxy_policy(self, message: dict[str, Any]) -> dict[str, Any]:
        method = str(message.get("method") or "")
        if method not in {"thread/start", "turn/start"}:
            return message
        outbound = json.loads(json.dumps(message))
        params = outbound.setdefault("params", {})
        if not isinstance(params, dict):
            params = {}
            outbound["params"] = params
        params["approvalPolicy"] = self.approval_policy
        params.setdefault("approvalsReviewer", "user")
        if method == "thread/start":
            params.pop("permissions", None)
            params["sandbox"] = self.sandbox
            params.pop("sandboxPolicy", None)
        else:
            params.pop("permissions", None)
            params.pop("sandbox", None)
            params["sandboxPolicy"] = _sandbox_policy_for_turn(self.sandbox)
        return outbound

    def _codex_remote_command(self) -> str:
        return (
            "AGENTLENS_DISABLE_HOOKS=1 codex "
            f"--ask-for-approval {self.approval_policy} "
            f"--sandbox {self.sandbox} "
            f"--remote ws://{self.proxy_host}:{self.proxy_port}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a local AgentLens proxy between Codex TUI and Codex app-server."
    )
    parser.add_argument("--repo", default=".", help="Repository path for Codex and AgentLens.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8787", help="AgentLens API URL.")
    parser.add_argument(
        "--dashboard-url",
        default="http://localhost:3000",
        help="AgentLens dashboard URL.",
    )
    parser.add_argument("--proxy-host", default="127.0.0.1", help="Proxy bind host.")
    parser.add_argument("--proxy-port", type=int, default=8791, help="Proxy WebSocket port.")
    parser.add_argument("--upstream-host", default="127.0.0.1", help="Upstream bind host.")
    parser.add_argument(
        "--upstream-port",
        type=int,
        default=8792,
        help="Upstream Codex app-server WebSocket port.",
    )
    parser.add_argument("--codex-binary", default="codex", help="Codex binary path.")
    parser.add_argument("--model", default=None, help="Optional Codex model override.")
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Codex sandbox policy.",
    )
    parser.add_argument(
        "--approval-policy",
        default="untrusted",
        choices=["untrusted", "on-request", "on-failure", "never"],
        help="Codex approval policy.",
    )
    parser.add_argument(
        "--no-enrich-native-prompt",
        action="store_true",
        help="Forward native approval prompts without injecting AgentLens summary text.",
    )
    args = parser.parse_args()

    proxy = CodexAppServerProxy(
        repo=args.repo,
        api_url=args.api_url,
        dashboard_url=args.dashboard_url,
        proxy_host=args.proxy_host,
        proxy_port=args.proxy_port,
        upstream_host=args.upstream_host,
        upstream_port=args.upstream_port,
        codex_binary=args.codex_binary,
        model=args.model,
        sandbox=args.sandbox,
        approval_policy=args.approval_policy,
        enrich_native_prompt=not args.no_enrich_native_prompt,
    )
    try:
        asyncio.run(proxy.run())
    except KeyboardInterrupt:
        print("\nAgentLens Codex proxy stopped.", file=sys.stderr)


def _decode_json(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, str):
        return None
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return message if isinstance(message, dict) else None


def _is_approval_request(message: dict[str, Any]) -> bool:
    return str(message.get("method") or "") in APPROVAL_METHODS and "id" in message


def _extract_prompt(params: dict[str, Any]) -> str | None:
    input_items = params.get("input")
    if isinstance(input_items, list):
        parts = [
            str(item.get("text"))
            for item in input_items
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
        ]
        if parts:
            return "\n".join(parts)
    prompt = params.get("prompt")
    return str(prompt) if prompt else None


def _native_approval_reason(
    proposal: ToolCallProposal,
    gate: dict[str, Any],
    *,
    repo: str,
) -> str:
    risk = gate.get("risk_assessment") if isinstance(gate.get("risk_assessment"), dict) else {}
    risk_level = str(risk.get("risk_level") or "unknown").strip().lower()
    evidence_items = risk.get("evidence")
    evidence = ""
    if isinstance(evidence_items, list):
        evidence = next((str(item).strip() for item in evidence_items if str(item).strip()), "")
    if not evidence:
        evidence = "no specific risk evidence recorded"
    return "  ".join(
        (
            f"AgentLens review: approve the proposed {_proposal_action_label(proposal, repo)} shown above?",
            f"Risk: {_sentence(risk_level)}",
            f"Why: {_sentence(evidence)}",
            "Open the AgentLens dashboard for full trajectory, drift, and policy context.",
        )
    )


def _passive_event_signature(proposal: ToolCallProposal) -> str:
    metadata = proposal.provider_metadata
    method = str(metadata.get("method") or "")
    item_id = _find_provider_value(metadata.get("raw_event"), {"itemId", "id"})
    if item_id:
        return f"{method}:{proposal.tool_name}:item:{item_id}"
    target = (
        proposal.params.get("command")
        or proposal.params.get("cmd")
        or proposal.params.get("path")
        or proposal.id
    )
    return f"{method}:{proposal.tool_name}:{target}"


def _target_hints_from_text(value: str) -> list[str]:
    hints = []
    for match in TARGET_HINT_RE.findall(value):
        cleaned = match.strip().strip("`'\".,:;()[]{}<>")
        if cleaned:
            hints.append(cleaned)
    return _unique_strings(hints)


def _proposal_target_hints(proposal: ToolCallProposal) -> list[str]:
    params = proposal.params
    values: list[str] = []
    paths = params.get("paths")
    if isinstance(paths, list):
        values.extend(str(path) for path in paths if str(path).strip())
    for key in ("path", "file", "target", "command", "cmd", "query"):
        value = params.get(key)
        if isinstance(value, str):
            values.append(value)
    metadata = proposal.provider_metadata
    values.extend(_collect_target_strings(metadata.get("raw_request")))
    values.extend(_collect_target_strings(metadata.get("raw_event")))
    values.extend(_target_hints_from_text(proposal.stated_reason or ""))
    hints: list[str] = []
    for value in values:
        hints.extend(_target_hints_from_text(str(value)))
    return _unique_strings(hints)


def _proposal_has_concrete_target(proposal: ToolCallProposal, repo: str) -> bool:
    params = proposal.params
    candidates: list[str] = []
    paths = params.get("paths")
    if isinstance(paths, list):
        candidates.extend(str(path) for path in paths if str(path).strip())
    for key in ("path", "file", "target"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value)
    repo_path = Path(repo).expanduser().resolve()
    for candidate in candidates:
        text = candidate.strip()
        if not text or text == "external state":
            continue
        try:
            if _is_repo_root_target(text, repo):
                continue
        except OSError:
            pass
        if text in {".", str(repo_path)}:
            continue
        return True
    return False


def _is_repo_root_target(value: str, repo: str) -> bool:
    text = value.strip()
    if text in {".", "external state"}:
        return text == "."
    path = Path(text).expanduser()
    if not path.is_absolute():
        return False
    try:
        return path.resolve() == Path(repo).expanduser().resolve()
    except OSError:
        return False


def _collect_target_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        strings = []
        for key, item in value.items():
            if key in {"path", "paths", "file", "files", "filePath", "file_path", "target"}:
                strings.extend(_collect_all_strings(item))
            else:
                strings.extend(_collect_target_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_collect_target_strings(item))
        return strings
    return []


def _collect_all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(_collect_all_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_collect_all_strings(item))
        return strings
    return []


def _unique_strings(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def _find_provider_value(value: Any, keys: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and item:
                return str(item)
        for item in value.values():
            found = _find_provider_value(item, keys)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_provider_value(item, keys)
            if found:
                return found
    return None


def _proposal_action_label(proposal: ToolCallProposal, repo: str) -> str:
    params = proposal.params
    if proposal.tool_name == "fs.write":
        return f"edit to {_target_path_label(params, repo)}"
    if proposal.tool_name == "fs.delete":
        return f"deletion of {_target_path_label(params, repo)}"
    if proposal.tool_name == "fs.read":
        return f"read of {_target_path_label(params, repo)}"
    if proposal.tool_name == "shell.run":
        command = str(params.get("command") or params.get("cmd") or "").strip()
        if command:
            return f"command `{command}`"
    target = _target_path_label(params, repo)
    if target != "the affected target":
        return f"{proposal.tool_name} action on {target}"
    return f"{proposal.tool_name} action"


def _target_path_label(params: dict[str, Any], repo: str) -> str:
    raw_path = (
        params.get("path")
        or params.get("grant_root")
        or params.get("grantRoot")
        or params.get("file")
        or params.get("target")
    )
    if not raw_path:
        return "the affected target"
    path_text = str(raw_path).strip()
    if not path_text:
        return "the affected target"
    if path_text == "external state":
        return path_text
    path = Path(path_text).expanduser()
    try:
        if path.is_absolute():
            return str(path.relative_to(Path(repo).expanduser()))
    except ValueError:
        return path.name or path_text
    return str(path)


def _sentence(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return "unknown."
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def _sandbox_policy_for_turn(sandbox: str) -> dict[str, Any]:
    if sandbox == "read-only":
        return {"type": "readOnly", "networkAccess": False}
    if sandbox == "danger-full-access":
        return {"type": "dangerFullAccess"}
    return {
        "type": "workspaceWrite",
        "writableRoots": [],
        "networkAccess": False,
        "excludeTmpdirEnvVar": False,
        "excludeSlashTmp": False,
    }


def _client_response_accepts(message: dict[str, Any]) -> bool:
    result = message.get("result")
    if not isinstance(result, dict):
        return False
    decision = result.get("decision")
    if isinstance(decision, str):
        return decision.lower() in {"accept", "approved", "approve", "allow", "yes"}
    permissions = result.get("permissions")
    if isinstance(permissions, dict):
        return bool(permissions)
    return False


if __name__ == "__main__":
    main()
