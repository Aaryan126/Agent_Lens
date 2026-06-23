import json

import httpx
import pytest

from agentlens.codex_proxy import AgentLensProxyState, CodexAppServerProxy, PendingNativeApproval


def _make_proxy() -> CodexAppServerProxy:
    return CodexAppServerProxy(
        repo="/repo",
        api_url="http://agentlens.test",
        dashboard_url="http://localhost:3000",
        proxy_host="127.0.0.1",
        proxy_port=8791,
        upstream_host="127.0.0.1",
        upstream_port=8792,
        codex_binary="codex",
        model=None,
        sandbox="workspace-write",
        approval_policy="untrusted",
        enrich_native_prompt=True,
    )


class FakeAsyncClient:
    responses: list[dict]
    requests: list[tuple[str, str, dict | None]]

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json):
        self.requests.append(("POST", url, json))
        request = httpx.Request("POST", url)
        if not self.responses:
            raise AssertionError(f"no fake response queued for {url}")
        return httpx.Response(200, json=self.responses.pop(0), request=request)

    async def get(self, url):
        self.requests.append(("GET", url, None))
        request = httpx.Request("GET", url)
        if not self.responses:
            raise httpx.ConnectError("AgentLens API down", request=request)
        return httpx.Response(200, json=self.responses.pop(0), request=request)


@pytest.fixture(autouse=True)
def fake_async_client(monkeypatch):
    FakeAsyncClient.responses = []
    FakeAsyncClient.requests = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


@pytest.mark.asyncio
async def test_proxy_creates_session_from_turn_start(fake_async_client) -> None:
    fake_async_client.responses.append({"id": "ses_proxy"})
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )

    await state.observe_client_message(
        {
            "method": "turn/start",
            "params": {"input": [{"type": "text", "text": "Edit README."}]},
        }
    )

    assert state.session_id == "ses_proxy"
    assert fake_async_client.requests[0][1] == "http://agentlens.test/sessions"
    assert fake_async_client.requests[0][2]["original_instruction"] == "Edit README."


@pytest.mark.asyncio
async def test_proxy_reuses_session_across_turns_in_same_remote_thread(
    fake_async_client,
) -> None:
    fake_async_client.responses.append({"id": "ses_proxy"})
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )

    await state.observe_client_message(
        {
            "method": "turn/start",
            "params": {"input": [{"type": "text", "text": "First prompt"}]},
        }
    )
    await state.observe_client_message(
        {
            "method": "turn/start",
            "params": {"input": [{"type": "text", "text": "Second prompt"}]},
        }
    )

    session_posts = [request for request in fake_async_client.requests if request[1].endswith("/sessions")]
    assert state.session_id == "ses_proxy"
    assert state.latest_prompt == "Second prompt"
    assert len(session_posts) == 1
    assert session_posts[0][2]["original_instruction"] == "First prompt"


@pytest.mark.asyncio
async def test_proxy_starts_new_agentlens_session_after_new_thread(
    fake_async_client,
) -> None:
    fake_async_client.responses.extend([{"id": "ses_first"}, {"id": "ses_second"}])
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )

    await state.observe_client_message(
        {"method": "turn/start", "params": {"input": [{"type": "text", "text": "First"}]}}
    )
    state.pending_native_approvals[7] = PendingNativeApproval(
        gate_id="gate_1",
        summary="Pending",
        tool_name="fs.write",
    )
    state.passive_event_signatures.add("item/started:shell.run:item_1")

    await state.observe_client_message({"method": "thread/start", "params": {}})
    await state.observe_client_message(
        {"method": "turn/start", "params": {"input": [{"type": "text", "text": "Second"}]}}
    )

    session_posts = [request for request in fake_async_client.requests if request[1].endswith("/sessions")]
    assert state.session_id == "ses_second"
    assert state.pending_native_approvals == {}
    assert state.passive_event_signatures == set()
    assert [request[2]["original_instruction"] for request in session_posts] == ["First", "Second"]


@pytest.mark.asyncio
async def test_proxy_enriches_pending_approval_request(fake_async_client) -> None:
    fake_async_client.responses.extend(
        [
            {"id": "ses_proxy"},
            {
                "id": "gate_1",
                "status": "pending",
                "intelligence_card": {"summary": "Review this write before it changes README."},
                "risk_assessment": {
                    "risk_level": "low",
                    "evidence": ["documentation-only change with limited blast radius"],
                },
            },
        ]
    )
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )
    await state.observe_client_message(
        {"method": "turn/start", "params": {"input": [{"type": "text", "text": "Task"}]}}
    )

    target, outbound = await state.handle_upstream_message(
        {
            "id": 7,
            "method": "item/fileChange/requestApproval",
            "params": {"itemId": "item_1", "grantRoot": "/repo/README.md"},
        }
    )

    assert target == "client"
    assert outbound["id"] == 7
    reason = outbound["params"]["reason"]
    assert "approve the proposed edit to README.md shown above" in reason
    assert "\n" not in reason
    assert "shown above?  Risk: low." in reason
    assert "Risk: low." in reason
    assert "Why: documentation-only change with limited blast radius." in reason
    assert "http://localhost" not in reason
    assert outbound["params"]["agentLens"]["gateId"] == "gate_1"
    assert "http://localhost:3000?" in outbound["params"]["agentLens"]["dashboardUrl"]
    assert state.pending_native_approvals[7].gate_id == "gate_1"


@pytest.mark.asyncio
async def test_proxy_reports_clear_error_when_agentlens_api_is_down(
    fake_async_client,
) -> None:
    proxy = _make_proxy()

    with pytest.raises(RuntimeError, match="Start the local guard first"):
        await proxy._wait_for_agentlens_api()


@pytest.mark.asyncio
async def test_proxy_agentlens_api_preflight_passes(fake_async_client) -> None:
    fake_async_client.responses.append({"status": "ok"})
    proxy = _make_proxy()

    await proxy._wait_for_agentlens_api()

    assert fake_async_client.requests[0][1] == "http://agentlens.test/health"


def test_proxy_policy_rewrite_deep_copies_thread_and_turn_starts() -> None:
    proxy = _make_proxy()
    original = {
        "method": "turn/start",
        "params": {
            "approvalPolicy": "never",
            "approvalsReviewer": "agent",
            "sandbox": "read-only",
            "permissions": "trusted-profile",
            "nested": {"items": [1]},
        },
    }

    rewritten = proxy._with_proxy_policy(original)

    assert rewritten is not original
    assert rewritten["params"] is not original["params"]
    assert rewritten["params"]["nested"] is not original["params"]["nested"]
    assert rewritten["params"]["approvalPolicy"] == "untrusted"
    assert "sandbox" not in rewritten["params"]
    assert "permissions" not in rewritten["params"]
    assert rewritten["params"]["sandboxPolicy"] == {
        "type": "workspaceWrite",
        "writableRoots": [],
        "networkAccess": False,
        "excludeTmpdirEnvVar": False,
        "excludeSlashTmp": False,
    }
    assert rewritten["params"]["approvalsReviewer"] == "agent"
    assert original["params"]["approvalPolicy"] == "never"
    assert original["params"]["sandbox"] == "read-only"
    assert original["params"]["permissions"] == "trusted-profile"

    thread_start = proxy._with_proxy_policy({"method": "thread/start", "params": "not-a-dict"})

    assert thread_start["params"] == {
        "approvalPolicy": "untrusted",
        "sandbox": "workspace-write",
        "approvalsReviewer": "user",
    }


def test_proxy_thread_start_uses_thread_sandbox_field() -> None:
    proxy = _make_proxy()

    rewritten = proxy._with_proxy_policy(
        {
            "method": "thread/start",
            "params": {
                "approvalPolicy": "never",
                "permissions": "profile",
                "sandboxPolicy": {"type": "readOnly"},
            },
        }
    )

    assert rewritten["params"]["approvalPolicy"] == "untrusted"
    assert rewritten["params"]["sandbox"] == "workspace-write"
    assert "sandboxPolicy" not in rewritten["params"]
    assert "permissions" not in rewritten["params"]


def test_proxy_remote_command_includes_explicit_policy_and_sandbox() -> None:
    proxy = _make_proxy()

    assert (
        proxy._codex_remote_command()
        == "AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted "
        "--sandbox workspace-write --remote ws://127.0.0.1:8791"
    )


@pytest.mark.asyncio
async def test_client_to_upstream_forwards_turn_start_with_proxy_policy() -> None:
    class FakeClient:
        def __init__(self, messages):
            self.messages = list(messages)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.messages:
                raise StopAsyncIteration
            return self.messages.pop(0)

    class FakeUpstream:
        def __init__(self):
            self.sent = []

        async def send(self, raw):
            self.sent.append(raw)

    class FakeState:
        def __init__(self):
            self.observed = []
            self.handled = []

        async def observe_client_message(self, message):
            self.observed.append(message)

        async def handle_client_message(self, message):
            self.handled.append(message)
            return message

    proxy = _make_proxy()
    client = FakeClient(['{"method":"turn/start","params":{"prompt":"Edit README."}}'])
    upstream = FakeUpstream()
    state = FakeState()

    await proxy._client_to_upstream(client, upstream, state)

    assert len(upstream.sent) == 1
    outbound = json.loads(upstream.sent[0])
    assert outbound["params"]["prompt"] == "Edit README."
    assert outbound["params"]["approvalPolicy"] == "untrusted"
    assert "sandbox" not in outbound["params"]
    assert outbound["params"]["sandboxPolicy"]["type"] == "workspaceWrite"
    assert outbound["params"]["approvalsReviewer"] == "user"


@pytest.mark.asyncio
async def test_proxy_auto_executed_gate_returns_upstream_accept(fake_async_client) -> None:
    fake_async_client.responses.extend(
        [
            {"id": "ses_proxy"},
            {
                "id": "gate_1",
                "status": "auto_executed",
                "intelligence_card": {"summary": "Safe read."},
            },
        ]
    )
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )

    target, outbound = await state.handle_upstream_message(
        {
            "id": 7,
            "method": "item/commandExecution/requestApproval",
            "params": {"command": "sed -n '1,80p' README.md", "cwd": "/repo"},
        }
    )

    assert target == "upstream"
    assert outbound == {"id": 7, "result": {"decision": "accept"}}
    assert state.pending_native_approvals == {}


@pytest.mark.asyncio
async def test_proxy_mirrors_passive_command_events_once(fake_async_client) -> None:
    fake_async_client.responses.extend(
        [
            {"id": "gate_passive", "status": "pending"},
            {"id": "gate_passive", "status": "auto_executed"},
            {"id": "gate_duplicate", "status": "auto_executed"},
        ]
    )
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )
    state.session_id = "ses_proxy"
    event = {
        "method": "item/started",
        "params": {
            "item": {
                "id": "item_1",
                "type": "commandExecution",
                "command": "rg --files",
                "cwd": "/repo",
            }
        },
    }

    target, outbound = await state.handle_upstream_message(event)
    duplicate_target, duplicate_outbound = await state.handle_upstream_message(event)

    assert target == "client"
    assert outbound == event
    assert duplicate_target == "client"
    assert duplicate_outbound == event
    tool_call_posts = [
        request for request in fake_async_client.requests if request[1].endswith("/tool-calls")
    ]
    assert len(tool_call_posts) == 1
    assert tool_call_posts[0][1] == "http://agentlens.test/sessions/ses_proxy/tool-calls"
    assert tool_call_posts[0][2]["tool_name"] == "shell.run"
    assert tool_call_posts[0][2]["params"]["command"] == "rg --files"
    assert tool_call_posts[0][2]["provider_metadata"]["passive"] is True
    observe_posts = [request for request in fake_async_client.requests if request[1].endswith("/observe")]
    assert len(observe_posts) == 1
    assert observe_posts[0][1] == "http://agentlens.test/gates/gate_passive/observe"


@pytest.mark.asyncio
async def test_proxy_does_not_mirror_ambiguous_file_change_events(fake_async_client) -> None:
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )
    state.session_id = "ses_proxy"

    target, outbound = await state.handle_upstream_message(
        {
            "method": "item/started",
            "params": {
                "item": {
                    "id": "item_file_change",
                    "type": "fileChange",
                    "path": "/repo/README.md",
                }
            },
        }
    )

    assert target == "client"
    assert outbound["method"] == "item/started"
    assert fake_async_client.requests == []


@pytest.mark.asyncio
async def test_proxy_records_native_accept_response_as_approve(fake_async_client) -> None:
    fake_async_client.responses.append({"id": "gate_1", "status": "approved"})
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )
    state.pending_native_approvals[7] = PendingNativeApproval(
        gate_id="gate_1",
        summary="Review.",
        tool_name="fs.write",
    )

    outbound = await state.handle_client_message({"id": 7, "result": {"decision": "accept"}})

    assert outbound["id"] == 7
    assert fake_async_client.requests[0][1] == "http://agentlens.test/gates/gate_1/approve"
    assert 7 not in state.pending_native_approvals


@pytest.mark.asyncio
async def test_proxy_resolves_stale_native_pending_gates_with_same_decision(
    fake_async_client,
) -> None:
    fake_async_client.responses.extend(
        [
            {"id": "gate_current", "status": "approved"},
            {"id": "gate_stale", "status": "approved"},
        ]
    )
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )
    state.pending_native_approvals[7] = PendingNativeApproval(
        gate_id="gate_current",
        summary="Current.",
        tool_name="fs.write",
    )
    state.pending_native_approvals[6] = PendingNativeApproval(
        gate_id="gate_stale",
        summary="Older.",
        tool_name="shell.run",
    )

    await state.handle_client_message({"id": 7, "result": {"decision": "accept"}})

    assert [request[1] for request in fake_async_client.requests] == [
        "http://agentlens.test/gates/gate_current/approve",
        "http://agentlens.test/gates/gate_stale/approve",
    ]
    assert state.pending_native_approvals == {}


@pytest.mark.asyncio
async def test_proxy_records_native_cancel_response_as_block(fake_async_client) -> None:
    fake_async_client.responses.append({"id": "gate_1", "status": "blocked"})
    state = AgentLensProxyState(
        api_url="http://agentlens.test",
        repo="/repo",
        dashboard_url="http://localhost:3000",
    )
    state.pending_native_approvals[7] = PendingNativeApproval(
        gate_id="gate_1",
        summary="Review.",
        tool_name="fs.write",
    )

    await state.handle_client_message({"id": 7, "result": {"decision": "cancel"}})

    assert fake_async_client.requests[0][1] == "http://agentlens.test/gates/gate_1/block"
    assert 7 not in state.pending_native_approvals
