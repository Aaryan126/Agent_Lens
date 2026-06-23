import httpx
import pytest

from agentlens.codex_hook import _proposal_from_hook, main as codex_hook_main


def test_codex_hook_parses_bash_payload() -> None:
    proposal = _proposal_from_hook(
        {"tool_name": "Bash", "input": {"command": "sed -n '1,80p' prd.md"}},
        event_name="PreToolUse",
        session_id="ses_hook",
        latest_prompt="Test prompt",
    )

    assert proposal is not None
    assert proposal.tool_name == "shell.run"
    assert proposal.params["command"] == "sed -n '1,80p' prd.md"
    assert proposal.params["agentlens_prompt"] == "Test prompt"
    assert proposal.provider_metadata["source"] == "codex_hook"
    assert proposal.provider_metadata["fast_intelligence"] is True


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
    assert requests[1][2]["params"]["command"] == "pwd"


def test_codex_hook_recovers_when_stored_session_is_missing(monkeypatch, tmp_path) -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []
    session_file = tmp_path / "session.json"
    session_file.write_text('{"session_id":"ses_stale","api_url":"http://127.0.0.1:8787"}')

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
            if url.endswith("/sessions/ses_stale/tool-calls"):
                return httpx.Response(404, json={"detail": "session not found"}, request=request)
            if url.endswith("/sessions"):
                return httpx.Response(200, json={"id": "ses_fresh"}, request=request)
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
            str(session_file),
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

    assert requests[0][1] == "http://127.0.0.1:8787/sessions/ses_stale/tool-calls"
    assert requests[1][1] == "http://127.0.0.1:8787/sessions"
    assert requests[2][1] == "http://127.0.0.1:8787/sessions/ses_fresh/tool-calls"
    assert requests[2][2]["session_id"] == "ses_fresh"


def test_user_prompt_submit_starts_fresh_session_without_posting_proposal(monkeypatch, tmp_path) -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []
    session_file = tmp_path / "session.json"
    session_file.write_text('{"session_id":"ses_old","recent_proposals":["abc"]}')

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
            return httpx.Response(200, json={"id": "ses_new"}, request=request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "agentlens-hook",
            "UserPromptSubmit",
            "--api-url",
            "http://127.0.0.1:8787",
            "--session-file",
            str(session_file),
            "--repo",
            str(tmp_path),
        ],
    )
    monkeypatch.setattr(
        "sys.stdin",
        type("FakeStdin", (), {"read": lambda self: '{"prompt":"Explain this repo."}'})(),
    )

    codex_hook_main()

    assert len(requests) == 1
    assert requests[0][1] == "http://127.0.0.1:8787/sessions"
    assert requests[0][2]["original_instruction"] == "Explain this repo."
    assert '"session_id": "ses_new"' in session_file.read_text(encoding="utf-8")
    assert '"recent_proposals": []' in session_file.read_text(encoding="utf-8")


def test_codex_hook_deduplicates_same_tool_payload(monkeypatch, tmp_path) -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []
    session_file = tmp_path / "session.json"

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
            return httpx.Response(200, json={"id": "gate_hook"}, request=request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    payload = '{"tool_name":"Bash","input":{"command":"pwd"}}'
    for event_name in ["PreToolUse", "PermissionRequest"]:
        monkeypatch.setattr(
            "sys.argv",
            [
                "agentlens-hook",
                event_name,
                "--api-url",
                "http://127.0.0.1:8787",
                "--session-file",
                str(session_file),
                "--repo",
                str(tmp_path),
            ],
        )
        monkeypatch.setattr(
            "sys.stdin",
            type("FakeStdin", (), {"read": lambda self, payload=payload: payload})(),
        )
        codex_hook_main()

    posted_tool_calls = [request for request in requests if request[1].endswith("/tool-calls")]
    assert len(posted_tool_calls) == 1


def test_codex_hook_waits_for_pending_gate_approval(monkeypatch, tmp_path) -> None:
    requests: list[tuple[str, str, dict[str, object] | None]] = []
    polls = {"count": 0}

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
                json={"id": "gate_pending", "status": "pending", "intelligence_card": {"summary": "Needs review."}},
                request=request,
            )

        def get(self, url: str):
            requests.append(("GET", url, None))
            polls["count"] += 1
            request = httpx.Request("GET", url)
            status = "approved" if polls["count"] >= 1 else "pending"
            return httpx.Response(200, json={"id": "gate_pending", "status": status}, request=request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("time.sleep", lambda _: None)
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
            "--approval-timeout",
            "2",
        ],
    )
    monkeypatch.setattr(
        "sys.stdin",
        type("FakeStdin", (), {"read": lambda self: '{"tool_name":"Bash","input":{"command":"touch notes.md"}}'})(),
    )

    codex_hook_main()

    assert any(request[0] == "GET" and request[1].endswith("/gates/gate_pending") for request in requests)


def test_codex_hook_blocks_when_gate_is_blocked(monkeypatch, tmp_path) -> None:
    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url: str, json: dict[str, object]):
            request = httpx.Request("POST", url)
            if url.endswith("/sessions"):
                return httpx.Response(200, json={"id": "ses_hook"}, request=request)
            return httpx.Response(
                200,
                json={"id": "gate_blocked", "status": "blocked", "intelligence_card": {"summary": "Do not delete."}},
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
        type("FakeStdin", (), {"read": lambda self: '{"tool_name":"Bash","input":{"command":"rm -rf backend/migrations"}}'})(),
    )

    with pytest.raises(SystemExit) as exc:
        codex_hook_main()

    assert exc.value.code == 2
