from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agentlens.dev_stack import DevStack


def _stack() -> DevStack:
    return DevStack(
        repo=Path("/tmp/repo"),
        project_root=Path("/tmp/agentlens"),
        api_host="127.0.0.1",
        api_port=8787,
        frontend_port=3000,
        proxy_port=8791,
        upstream_port=8792,
        codex_binary="codex",
        launch_codex=True,
        open_dashboard=False,
    )


def test_codex_command_uses_proxy_approval_and_sandbox_flags() -> None:
    assert _stack().codex_command() == [
        "codex",
        "--ask-for-approval",
        "untrusted",
        "--sandbox",
        "workspace-write",
        "--remote",
        "ws://127.0.0.1:8791",
    ]


def test_stack_urls_use_configured_ports() -> None:
    stack = _stack()

    assert stack.api_url == "http://127.0.0.1:8787"
    assert stack.frontend_url == "http://localhost:3000"
    assert stack.proxy_url == "ws://127.0.0.1:8791"


def test_nonzero_codex_exit_keeps_stack_running(monkeypatch) -> None:
    stack = _stack()
    waited = {"called": False}

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1)

    def fake_wait_forever():
        waited["called"] = True

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(stack, "_wait_forever", fake_wait_forever)

    stack._run_codex()

    assert waited["called"] is True
