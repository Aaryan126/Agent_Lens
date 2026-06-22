import subprocess
from types import SimpleNamespace

import httpx

from agentlens.adapters.codex_cli import CodexCliAdapter, parse_codex_jsonl
from agentlens.cli import _run_remote
from agentlens.codex_terminal import main as codex_terminal_main


def test_parse_codex_jsonl_extracts_tool_call_proposal() -> None:
    proposals = parse_codex_jsonl(
        [
            '{"type":"tool_call","name":"shell","call":{"arguments":{"cmd":"pytest"}}}',
            '{"type":"message","content":"done"}',
        ],
        session_id="ses_test",
    )

    assert len(proposals) == 1
    assert proposals[0].tool_name == "shell.run"
    assert proposals[0].params == {"cmd": "pytest"}


def test_parse_real_codex_command_execution_started_event() -> None:
    proposals = parse_codex_jsonl(
        [
            '{"type":"thread.started","thread_id":"abc"}',
            '{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc \\"pwd && rg --files\\"","aggregated_output":"","exit_code":null,"status":"in_progress"}}',
            '{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc \\"pwd && rg --files\\"","aggregated_output":"README.md","exit_code":0,"status":"completed"}}',
        ],
        session_id="ses_test",
    )

    assert len(proposals) == 1
    assert proposals[0].tool_name == "shell.run"
    assert proposals[0].params["command"] == '/bin/zsh -lc "pwd && rg --files"'
    assert proposals[0].provider_metadata["event_type"] == "item.started"


def test_parse_real_codex_file_change_started_event() -> None:
    proposals = parse_codex_jsonl(
        [
            '{"type":"item.started","item":{"id":"item_1","type":"file_change","changes":[{"path":"/tmp/hello.txt","kind":"add"},{"path":"/tmp/old.txt","kind":"delete"}],"status":"in_progress"}}',
            '{"type":"item.completed","item":{"id":"item_1","type":"file_change","changes":[{"path":"/tmp/hello.txt","kind":"add"}],"status":"completed"}}',
        ],
        session_id="ses_test",
    )

    assert len(proposals) == 2
    assert proposals[0].tool_name == "fs.write"
    assert proposals[0].params == {"path": "/tmp/hello.txt", "kind": "add"}
    assert proposals[1].tool_name == "fs.delete"
    assert proposals[1].params == {"path": "/tmp/old.txt", "kind": "delete"}


def test_codex_cli_adapter_builds_read_only_json_command(tmp_path) -> None:
    captured = {}

    def runner(command, cwd, timeout_seconds):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout_seconds"] = timeout_seconds
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"type":"tool_call","name":"read","input":{"path":"prd.md"}}\n',
            stderr="",
        )

    result = CodexCliAdapter(runner=runner).run(
        prompt="Inspect only.",
        session_id="ses_test",
        cwd=str(tmp_path),
        model="gpt-5.4",
        sandbox="workspace-write",
        timeout_seconds=5,
    )

    assert result.returncode == 0
    assert result.proposals[0].tool_name == "fs.read"
    assert captured["command"][:3] == ["codex", "exec", "--json"]
    assert "--sandbox" in captured["command"]
    assert "workspace-write" in captured["command"]


def test_remote_codex_mode_posts_parsed_proposals(monkeypatch, tmp_path) -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url: str, json: dict[str, object]):
            requests.append(("POST", url, json))
            request = httpx.Request("POST", url)
            if url.endswith("/sessions"):
                return httpx.Response(200, json={"id": "ses_remote"}, request=request)
            return httpx.Response(
                200,
                json={"id": "gate_1", "status": "auto_executed"},
                request=request,
            )

    def fake_run(self, **kwargs):
        class Result:
            stderr = ""
            proposals = parse_codex_jsonl(
                [
                    '{"type":"item.started","item":{"type":"command_execution","command":"pwd","status":"in_progress"}}'
                ],
                session_id=kwargs["session_id"],
            )

        return Result()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr(CodexCliAdapter, "run", fake_run)

    args = SimpleNamespace(
        api_url="https://agentlens.example",
        session_id=None,
        instruction="Inspect the repo.",
        repo=str(tmp_path),
        codex_prompt="Run pwd.",
        codex_model=None,
        codex_sandbox="read-only",
        fixture=None,
    )

    _run_remote(args)

    assert requests[0][1] == "https://agentlens.example/sessions"
    assert requests[1][1] == "https://agentlens.example/sessions/ses_remote/tool-calls"
    assert requests[1][2]["session_id"] == "ses_remote"
    assert requests[1][2]["tool_name"] == "shell.run"


def test_agentlens_codex_command_creates_session_and_posts(monkeypatch, tmp_path, capsys) -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url: str, json: dict[str, object]):
            requests.append(("POST", url, json))
            request = httpx.Request("POST", url)
            if url.endswith("/sessions"):
                return httpx.Response(200, json={"id": "ses_terminal"}, request=request)
            return httpx.Response(
                200,
                json={"id": "gate_terminal", "status": "auto_executed"},
                request=request,
            )

    def fake_run(self, **kwargs):
        class Result:
            returncode = 0
            stderr = ""
            stdout = (
                '{"type":"item.started","item":{"type":"command_execution","command":"pwd","status":"in_progress"}}\n'
            )
            proposals = parse_codex_jsonl(stdout.splitlines(), session_id=kwargs["session_id"])

        return Result()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr(CodexCliAdapter, "run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentlens-codex",
            "--repo",
            str(tmp_path),
            "--api-url",
            "http://127.0.0.1:8787",
            "What is this repo about?",
        ],
    )

    try:
        codex_terminal_main()
    except SystemExit as exc:
        assert exc.code == 0

    assert requests[0][1] == "http://127.0.0.1:8787/sessions"
    assert requests[1][1] == "http://127.0.0.1:8787/sessions/ses_terminal/tool-calls"
    assert requests[1][2]["tool_name"] == "shell.run"
    output = capsys.readouterr().out
    assert "Dashboard:         http://localhost:3000?session=ses_terminal" in output
