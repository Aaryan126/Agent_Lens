import httpx

from agentlens.adapters.codex_app_server import (
    AppServerApproval,
    CodexAppServerAdapter,
    proposal_from_app_server_request,
)
from agentlens.app_server_terminal import AgentLensApprovalBridge
from agentlens.schemas import GateStatus


class FakeTransport:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []
        self.closed = False

    def send(self, message):
        self.sent.append(message)

    def read(self):
        if not self.messages:
            return None
        return self.messages.pop(0)

    def close(self):
        self.closed = True


def test_proposal_from_command_approval_request() -> None:
    proposal = proposal_from_app_server_request(
        method="item/commandExecution/requestApproval",
        session_id="ses_app",
        params={
            "command": "python -m pytest",
            "cwd": "/repo",
            "itemId": "item_1",
            "reason": "Need to run tests.",
        },
    )

    assert proposal.tool_name == "shell.run"
    assert proposal.params["command"] == "python -m pytest"
    assert proposal.provider_metadata["source"] == "codex_app_server"


def test_proposal_from_nested_command_approval_request() -> None:
    proposal = proposal_from_app_server_request(
        method="item/commandExecution/requestApproval",
        session_id="ses_app",
        params={
            "item": {
                "type": "commandExecution",
                "command": "sed -n '1,80p' README.md",
                "cwd": "/repo",
            },
            "itemId": "item_1",
            "reason": "Need to inspect README.",
        },
    )

    assert proposal.tool_name == "shell.run"
    assert proposal.params["command"] == "sed -n '1,80p' README.md"
    assert proposal.params["cwd"] == "/repo"


def test_app_server_adapter_answers_approval_requests() -> None:
    transport = FakeTransport(
        [
            {"id": 1, "result": {"userAgent": "test"}},
            {"id": 2, "result": {"thread": {"id": "thr_1"}}},
            {"id": 3, "result": {"turn": {"id": "turn_1"}}},
            {
                "method": "item/commandExecution/requestApproval",
                "id": 4,
                "params": {
                    "command": "touch README.md",
                    "cwd": "/repo",
                    "itemId": "item_1",
                    "threadId": "thr_1",
                    "turnId": "turn_1",
                    "startedAtMs": 1,
                },
            },
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr_1",
                    "turn": {"id": "turn_1", "status": "completed"},
                },
            },
        ]
    )
    approvals = []

    def approve(proposal, request):
        approvals.append((proposal, request))
        return AppServerApproval(decision=GateStatus.APPROVED, gate_id="gate_1")

    result = CodexAppServerAdapter(transport_factory=lambda cwd: transport).run_turn(
        prompt="Edit README.",
        session_id="ses_app",
        cwd="/repo",
        approval_handler=approve,
    )

    assert result.thread_id == "thr_1"
    assert result.final_status == "completed"
    assert approvals[0][0].tool_name == "shell.run"
    assert {"id": 4, "result": {"decision": "accept"}} in transport.sent
    assert transport.closed is True


def test_agentlens_approval_bridge_polls_pending_gate(monkeypatch) -> None:
    requests = []

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, json):
            requests.append(("POST", url, json))
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={
                    "id": "gate_1",
                    "status": "pending",
                    "intelligence_card": {"summary": "Review write."},
                },
                request=request,
            )

        def get(self, url):
            requests.append(("GET", url, None))
            request = httpx.Request("GET", url)
            return httpx.Response(200, json={"id": "gate_1", "status": "approved"}, request=request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("time.sleep", lambda _: None)
    proposal = proposal_from_app_server_request(
        method="item/fileChange/requestApproval",
        session_id="ses_app",
        params={"itemId": "item_1", "grantRoot": "/repo/README.md"},
    )

    approval = AgentLensApprovalBridge(
        api_url="http://127.0.0.1:8787",
        session_id="ses_app",
        approval_timeout=5,
    ).handle(proposal, {"id": 1})

    assert approval.decision == GateStatus.APPROVED
    assert any(request[0] == "GET" and request[1].endswith("/gates/gate_1") for request in requests)


def test_agentlens_approval_bridge_accepts_terminal_decision(monkeypatch) -> None:
    requests = []

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, json):
            requests.append(("POST", url, json))
            request = httpx.Request("POST", url)
            if url.endswith("/tool-calls"):
                return httpx.Response(
                    200,
                    json={
                        "id": "gate_1",
                        "status": "pending",
                        "intelligence_card": {"summary": "Review write."},
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={"id": "gate_1", "status": "approved", "human_reason": json["reason"]},
                request=request,
            )

        def get(self, url):
            requests.append(("GET", url, None))
            request = httpx.Request("GET", url)
            return httpx.Response(200, json={"id": "gate_1", "status": "pending"}, request=request)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    proposal = proposal_from_app_server_request(
        method="item/fileChange/requestApproval",
        session_id="ses_app",
        params={"itemId": "item_1", "grantRoot": "/repo/README.md"},
    )

    approval = AgentLensApprovalBridge(
        api_url="http://127.0.0.1:8787",
        session_id="ses_app",
        approval_timeout=5,
        terminal_decision_reader=lambda: ("approve", None),
    ).handle(proposal, {"id": 1})

    assert approval.decision == GateStatus.APPROVED
    assert any(request[0] == "POST" and request[1].endswith("/gates/gate_1/approve") for request in requests)
    assert not any(request[0] == "GET" for request in requests)
