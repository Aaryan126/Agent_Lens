import subprocess

from agentlens.adapters.codex_cli import CodexCliAdapter, parse_codex_jsonl


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
