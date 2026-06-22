import httpx

from agentlens.codex_hook import _proposal_from_hook, main as codex_hook_main


def test_codex_hook_parses_bash_payload() -> None:
    proposal = _proposal_from_hook(
        {"tool_name": "Bash", "input": {"command": "sed -n '1,80p' prd.md"}},
        event_name="PreToolUse",
        session_id="ses_hook",
    )

    assert proposal is not None
    assert proposal.tool_name == "shell.run"
    assert proposal.params == {"command": "sed -n '1,80p' prd.md"}
    assert proposal.provider_metadata["source"] == "codex_hook"


def test_codex_hook_creates_session_and_posts(monkeypatch, tmp_path) -> None:
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
                return httpx.Response(200, json={"id": "ses_hook"}, request=request)
            return httpx.Response(
                200,
                json={"id": "gate_hook", "status": "auto_executed"},
                request=request,
            )

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentlens-hook",
            "PreToolUse",
            "--api-url",
            "http://127.0.0.1:8787",
            "--session-file",
            str(tmp_path / "session.json"),
            "--repo",
            str(tmp_path),
        ],
    )
    monkeypatch.setattr(
        "sys.stdin",
        type(
            "FakeStdin",
            (),
            {"read": lambda self: '{"tool_name":"Bash","input":{"command":"pwd"}}'},
        )(),
    )

    codex_hook_main()

    assert requests[0][1] == "http://127.0.0.1:8787/sessions"
    assert requests[1][1] == "http://127.0.0.1:8787/sessions/ses_hook/tool-calls"
    assert requests[1][2]["tool_name"] == "shell.run"
    assert requests[1][2]["params"] == {"command": "pwd"}
