from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from agentlens.schemas import GateStatus, ToolCallProposal


class JsonRpcTransport(Protocol):
    def send(self, message: dict[str, Any]) -> None: ...

    def read(self) -> dict[str, Any] | None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class AppServerApproval:
    decision: GateStatus
    gate_id: str | None = None
    summary: str | None = None


ApprovalHandler = Callable[[ToolCallProposal, dict[str, Any]], AppServerApproval]
EventHandler = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class CodexAppServerResult:
    thread_id: str | None
    turn_id: str | None
    final_status: str | None
    proposals: list[ToolCallProposal] = field(default_factory=list)


class SubprocessJsonRpcTransport:
    """JSONL transport for `codex app-server --stdio`."""

    def __init__(self, *, binary: str = "codex", cwd: str | None = None) -> None:
        self.process = subprocess.Popen(
            [binary, "app-server", "--stdio"],
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def send(self, message: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError("Codex app-server stdin is closed.")
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def read(self) -> dict[str, Any] | None:
        if self.process.stdout is None:
            return None
        line = self.process.stdout.readline()
        if not line:
            return None
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            return {"method": "agentlens/nonJsonOutput", "params": {"line": line.rstrip()}}
        return value if isinstance(value, dict) else None

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


class CodexAppServerAdapter:
    """Small JSON-RPC client for Codex app-server turns and approval callbacks."""

    def __init__(
        self,
        *,
        binary: str = "codex",
        transport_factory: Callable[[str], JsonRpcTransport] | None = None,
    ) -> None:
        self.binary = binary
        self.transport_factory = transport_factory

    def run_turn(
        self,
        *,
        prompt: str,
        session_id: str,
        cwd: str,
        approval_handler: ApprovalHandler,
        event_handler: EventHandler | None = None,
        model: str | None = None,
        sandbox: str = "workspace-write",
        approval_policy: str = "untrusted",
        timeout_seconds: int = 600,
    ) -> CodexAppServerResult:
        transport = self._transport(cwd)
        request_id = 1
        thread_id: str | None = None
        turn_id: str | None = None
        final_status: str | None = None
        proposals: list[ToolCallProposal] = []
        pending_responses: dict[int, dict[str, Any]] = {}

        def send_request(method: str, params: dict[str, Any]) -> int:
            nonlocal request_id
            current = request_id
            request_id += 1
            transport.send({"method": method, "id": current, "params": params})
            return current

        try:
            initialize_id = send_request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "agentlens_guarded_terminal",
                        "title": "AgentLens Guarded Terminal",
                        "version": "0.1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            self._wait_for_response(
                transport,
                initialize_id,
                pending_responses,
                event_handler=event_handler,
                timeout_seconds=timeout_seconds,
            )
            transport.send({"method": "initialized", "params": {}})

            thread_id_request = send_request(
                "thread/start",
                {
                    "cwd": str(Path(cwd)),
                    "model": model,
                    "sandbox": sandbox,
                    "approvalPolicy": approval_policy,
                    "approvalsReviewer": "user",
                    "threadSource": "exec",
                },
            )
            thread_response = self._wait_for_response(
                transport,
                thread_id_request,
                pending_responses,
                event_handler=event_handler,
                timeout_seconds=timeout_seconds,
            )
            thread_id = _extract_thread_id(thread_response)
            if not thread_id:
                raise RuntimeError(f"Codex app-server did not return a thread id: {thread_response}")

            turn_request = send_request(
                "turn/start",
                {
                    "threadId": thread_id,
                    "cwd": str(Path(cwd)),
                    "model": model,
                    "approvalPolicy": approval_policy,
                    "input": [{"type": "text", "text": prompt}],
                },
            )
            self._wait_for_response(
                transport,
                turn_request,
                pending_responses,
                event_handler=event_handler,
                timeout_seconds=timeout_seconds,
            )

            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                message = transport.read()
                if message is None:
                    break
                if "id" in message and "method" not in message:
                    pending_responses[int(message["id"])] = message
                    continue

                method = str(message.get("method") or "")
                params = message.get("params") if isinstance(message.get("params"), dict) else {}

                if _is_approval_request(message):
                    proposal = proposal_from_app_server_request(
                        method=method,
                        params=params,
                        session_id=session_id,
                    )
                    proposals.append(proposal)
                    approval = approval_handler(proposal, message)
                    transport.send(_approval_response(message, approval))
                    continue

                if method == "turn/started":
                    turn_id = _find_first_string(params, {"id", "turnId"})
                elif method == "turn/completed":
                    turn_id = turn_id or _find_first_string(params, {"id", "turnId"})
                    final_status = _turn_status(params)
                    if event_handler:
                        event_handler(message)
                    break

                if event_handler:
                    event_handler(message)
            else:
                raise TimeoutError(f"Codex app-server turn exceeded {timeout_seconds} seconds.")
        finally:
            transport.close()

        return CodexAppServerResult(
            thread_id=thread_id,
            turn_id=turn_id,
            final_status=final_status,
            proposals=proposals,
        )

    def _transport(self, cwd: str) -> JsonRpcTransport:
        if self.transport_factory is not None:
            return self.transport_factory(cwd)
        return SubprocessJsonRpcTransport(binary=self.binary, cwd=cwd)

    def _wait_for_response(
        self,
        transport: JsonRpcTransport,
        request_id: int,
        pending_responses: dict[int, dict[str, Any]],
        *,
        event_handler: EventHandler | None,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        if request_id in pending_responses:
            return pending_responses.pop(request_id)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            message = transport.read()
            if message is None:
                break
            if "id" in message and "method" not in message:
                response_id = int(message["id"])
                if response_id == request_id:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message
                pending_responses[response_id] = message
                continue
            if event_handler:
                event_handler(message)
        raise TimeoutError(f"Timed out waiting for Codex app-server response {request_id}.")


def proposal_from_app_server_request(
    *, method: str, params: dict[str, Any], session_id: str
) -> ToolCallProposal:
    if method == "item/commandExecution/requestApproval":
        command = _find_first_string(params, {"command", "cmd"})
        cwd = _find_first_string(params, {"cwd"})
        return ToolCallProposal(
            session_id=session_id,
            tool_name="shell.run",
            params={
                "command": command,
                "cwd": cwd,
                "command_actions": params.get("commandActions") or [],
                "approval_id": params.get("approvalId"),
                "item_id": params.get("itemId"),
            },
            stated_reason=params.get("reason") or "Codex requested approval to run a command.",
            provider_metadata={
                "source": "codex_app_server",
                "method": method,
                "raw_request": params,
            },
        )

    if method == "item/fileChange/requestApproval":
        paths = _find_all_strings(
            params,
            {
                "path",
                "paths",
                "file",
                "files",
                "filePath",
                "file_path",
                "relativePath",
                "target",
                "targets",
            },
        )
        grant_root = _find_first_string(params, {"grantRoot", "grant_root"})
        if grant_root:
            paths.append(grant_root)
        paths = _unique_strings(paths)
        return ToolCallProposal(
            session_id=session_id,
            tool_name="fs.write",
            params={
                "path": paths[0] if paths else "external state",
                "paths": paths,
                "grant_root": grant_root,
                "item_id": params.get("itemId"),
            },
            stated_reason=params.get("reason") or "Codex requested approval to change files.",
            provider_metadata={
                "source": "codex_app_server",
                "method": method,
                "raw_request": params,
            },
        )

    return ToolCallProposal(
        session_id=session_id,
        tool_name="api.call",
        params={
            "approval_method": method,
            "permissions": params.get("permissions"),
            "reason": params.get("reason"),
            "item_id": params.get("itemId"),
        },
        stated_reason=params.get("reason") or f"Codex requested approval through {method}.",
        provider_metadata={
            "source": "codex_app_server",
            "method": method,
            "raw_request": params,
        },
    )


def proposal_from_app_server_event(
    *, method: str, params: dict[str, Any], session_id: str
) -> ToolCallProposal | None:
    """Best-effort conversion for non-blocking app-server telemetry events."""

    if method == "item/started":
        item = params.get("item") if isinstance(params.get("item"), dict) else {}
        item_type = _item_type(item)
        if item_type == "commandExecution":
            command = _find_first_string(item, {"command", "cmd"})
            if not command:
                return None
            return _passive_shell_proposal(
                session_id=session_id,
                method=method,
                command=command,
                cwd=_find_first_string(item, {"cwd"}),
                raw_event=params,
            )
        if item_type == "fileChange":
            path = _find_first_string(item, {"path", "file", "filePath", "grantRoot"})
            if not path:
                return None
            return _passive_file_proposal(
                session_id=session_id,
                method=method,
                path=path,
                raw_event=params,
                operation=_find_first_string(item, {"operation", "kind", "changeType"}),
            )

    if "commandExecution" in method or method in {"command/exec/outputDelta"}:
        command = _find_first_string(params, {"command", "cmd"})
        if command:
            return _passive_shell_proposal(
                session_id=session_id,
                method=method,
                command=command,
                cwd=_find_first_string(params, {"cwd"}),
                raw_event=params,
            )

    return None


def _approval_response(
    request: dict[str, Any],
    approval: AppServerApproval,
) -> dict[str, Any]:
    return approval_response_for_app_server_request(request, approval)


def approval_response_for_app_server_request(
    request: dict[str, Any],
    approval: AppServerApproval,
) -> dict[str, Any]:
    request_id = request.get("id")
    method = str(request.get("method") or "")
    accept = approval.decision in {
        GateStatus.APPROVED,
        GateStatus.MODIFIED,
        GateStatus.AUTO_EXECUTED,
    }
    if method == "item/commandExecution/requestApproval":
        return {"id": request_id, "result": {"decision": "accept" if accept else "cancel"}}
    if method == "item/fileChange/requestApproval":
        return {"id": request_id, "result": {"decision": "accept" if accept else "cancel"}}
    if method == "item/permissions/requestApproval":
        permissions = (request.get("params") or {}).get("permissions") if accept else {}
        return {
            "id": request_id,
            "result": {
                "permissions": _granted_permissions(permissions),
                "scope": "turn",
                "strictAutoReview": True,
            },
        }
    return {
        "id": request_id,
        "error": {
            "code": -32000,
            "message": "AgentLens does not support this app-server approval request yet.",
        },
    }


def _granted_permissions(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "fileSystem": value.get("fileSystem"),
            "network": value.get("network"),
        }
    return {"fileSystem": None, "network": None}


def _is_approval_request(message: dict[str, Any]) -> bool:
    return str(message.get("method") or "") in {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
        "item/permissions/requestApproval",
    } and "id" in message


def _extract_thread_id(response: dict[str, Any]) -> str | None:
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    thread = result.get("thread")
    if isinstance(thread, dict):
        thread_id = thread.get("id")
        return str(thread_id) if thread_id else None
    thread_id = result.get("threadId")
    return str(thread_id) if thread_id else None


def _turn_status(params: dict[str, Any]) -> str | None:
    turn = params.get("turn")
    if isinstance(turn, dict):
        status = turn.get("status")
        return str(status) if status else None
    status = params.get("status")
    return str(status) if status else None


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


def _find_all_strings(value: Any, keys: set[str]) -> list[str]:
    found: list[str] = []
    _collect_matching_strings(value, keys, found)
    return found


def _collect_matching_strings(value: Any, keys: set[str], output: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                _collect_all_strings(item, output)
            else:
                _collect_matching_strings(item, keys, output)
        return
    if isinstance(value, list):
        for item in value:
            _collect_matching_strings(item, keys, output)


def _collect_all_strings(value: Any, output: list[str]) -> None:
    if isinstance(value, str) and value.strip():
        output.append(value.strip())
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_all_strings(item, output)
        return
    if isinstance(value, list):
        for item in value:
            _collect_all_strings(item, output)


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _item_type(item: dict[str, Any]) -> str | None:
    item_type = item.get("type")
    if isinstance(item_type, dict):
        item_type = next(iter(item_type.keys()), None)
    return str(item_type) if item_type else None


def _passive_shell_proposal(
    *,
    session_id: str,
    method: str,
    command: str,
    cwd: str | None,
    raw_event: dict[str, Any],
) -> ToolCallProposal:
    return ToolCallProposal(
        session_id=session_id,
        tool_name="shell.run",
        params={"command": command, "cwd": cwd},
        stated_reason="Codex app-server reported a shell command event.",
        provider_metadata={
            "source": "codex_app_server_event",
            "method": method,
            "passive": True,
            "raw_event": raw_event,
        },
    )


def _passive_file_proposal(
    *,
    session_id: str,
    method: str,
    path: str,
    raw_event: dict[str, Any],
    operation: str | None,
) -> ToolCallProposal | None:
    operation_label = (operation or "").lower()
    if any(token in operation_label for token in ("write", "edit", "create", "change", "delete", "remove")):
        return None
    if not any(token in operation_label for token in ("read", "inspect", "view", "open")):
        return None
    tool_name = "fs.read"
    return ToolCallProposal(
        session_id=session_id,
        tool_name=tool_name,
        params={"path": path},
        stated_reason="Codex app-server reported a file inspection event.",
        provider_metadata={
            "source": "codex_app_server_event",
            "method": method,
            "passive": True,
            "raw_event": raw_event,
        },
    )
