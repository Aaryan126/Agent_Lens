from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from agentlens.adapters.codex_cli import CodexCliAdapter
from agentlens.schemas import SessionStart, ToolCallProposal
from agentlens.session import AgentLensSession
from agentlens.simulator import default_demo_proposals
from agentlens.slack import post_gate_message, render_gate_message
from agentlens.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local AgentLens simulator session.")
    parser.add_argument("--repo", default="..", help="Repository path to inspect.")
    parser.add_argument(
        "--instruction",
        default="Implement AgentLens safely and ask for approval before risky actions.",
        help="Original user instruction for the simulated session.",
    )
    parser.add_argument(
        "--fixture",
        default=None,
        help="Optional JSON file containing a list of tool-call proposal objects.",
    )
    parser.add_argument(
        "--slack",
        action="store_true",
        help="Print Slack Block Kit message JSON for pending gates.",
    )
    parser.add_argument(
        "--slack-send-channel",
        default=None,
        help="Post pending gate cards to this Slack channel ID using SLACK_BOT_TOKEN.",
    )
    parser.add_argument(
        "--codex-prompt",
        default=None,
        help="Run Codex CLI in read-only JSON mode and gate any parsed tool-call proposals.",
    )
    parser.add_argument(
        "--codex-model",
        default=None,
        help="Optional model name to pass to codex exec.",
    )
    parser.add_argument(
        "--codex-sandbox",
        default="read-only",
        choices=["read-only", "workspace-write"],
        help="Sandbox mode to pass to codex exec. Defaults to read-only.",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Optional AgentLens API URL. When set, parsed Codex proposals are posted to the API.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Existing AgentLens session ID to use with --api-url.",
    )
    args = parser.parse_args()

    if args.api_url:
        _run_remote(args)
        return

    session = AgentLensSession.start(
        SessionStart(original_instruction=args.instruction, repo_path=args.repo)
    )
    if args.codex_prompt:
        result = CodexCliAdapter().run(
            prompt=args.codex_prompt,
            session_id=session.session.id,
            cwd=args.repo,
            model=args.codex_model,
            sandbox=args.codex_sandbox,
        )
        if result.stderr:
            print(result.stderr)
        proposals = result.proposals
    elif args.fixture:
        proposals = _load_fixture(args.fixture, session.session.id)
    else:
        proposals = default_demo_proposals(session.session.id)

    for proposal in proposals:
        gate = session.propose(proposal)
        print(
            json.dumps(
                {
                    "proposal_id": proposal.id,
                    "tool": proposal.tool_name,
                    "gate_status": gate.status,
                    "policy": gate.policy_decision.model_dump(),
                    "risk": gate.risk_assessment.model_dump(),
                    "card": gate.intelligence_card.model_dump() if gate.intelligence_card else None,
                },
                default=str,
                indent=2,
            )
        )
        if args.slack and gate.status == "pending":
            print(json.dumps(render_gate_message(gate), default=str, indent=2))
        if args.slack_send_channel and gate.status == "pending":
            settings = load_settings()
            result = post_gate_message(
                bot_token=settings.slack_bot_token,
                channel_id=args.slack_send_channel,
                gate=gate,
            )
            print(json.dumps({"slack_posted": True, "channel": result.get("channel"), "ts": result.get("ts")}, indent=2))


def _run_remote(args: argparse.Namespace) -> None:
    api_url = str(args.api_url).rstrip("/")
    with httpx.Client(timeout=180) as client:
        session_id = args.session_id
        if session_id is None:
            response = client.post(
                f"{api_url}/sessions",
                json={
                    "original_instruction": args.instruction,
                    "repo_path": str(Path(args.repo)),
                },
            )
            response.raise_for_status()
            session_id = response.json()["id"]
            print(json.dumps({"session_id": session_id, "created": True}, indent=2))

        if args.codex_prompt:
            result = CodexCliAdapter().run(
                prompt=args.codex_prompt,
                session_id=session_id,
                cwd=args.repo,
                model=args.codex_model,
                sandbox=args.codex_sandbox,
            )
            if result.stderr:
                print(result.stderr)
            proposals = result.proposals
        elif args.fixture:
            proposals = _load_fixture(args.fixture, session_id)
        else:
            proposals = default_demo_proposals(session_id)

        for proposal in proposals:
            response = client.post(
                f"{api_url}/sessions/{session_id}/tool-calls",
                json=proposal.model_dump(mode="json"),
            )
            response.raise_for_status()
            gate = response.json()
            print(
                json.dumps(
                    {
                        "session_id": session_id,
                        "proposal_id": proposal.id,
                        "tool": proposal.tool_name,
                        "gate_id": gate["id"],
                        "gate_status": gate["status"],
                    },
                    indent=2,
                )
            )


def _load_fixture(path: str, session_id: str) -> list[ToolCallProposal]:
    raw_items = json.loads(Path(path).read_text())
    return [ToolCallProposal(session_id=session_id, **item) for item in raw_items]
