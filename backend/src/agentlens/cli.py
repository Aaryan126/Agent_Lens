from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentlens.schemas import SessionStart, ToolCallProposal
from agentlens.session import AgentLensSession
from agentlens.simulator import default_demo_proposals


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
    args = parser.parse_args()

    session = AgentLensSession.start(
        SessionStart(original_instruction=args.instruction, repo_path=args.repo)
    )
    proposals = _load_fixture(args.fixture, session.session.id) if args.fixture else default_demo_proposals(
        session.session.id
    )

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


def _load_fixture(path: str, session_id: str) -> list[ToolCallProposal]:
    raw_items = json.loads(Path(path).read_text())
    return [ToolCallProposal(session_id=session_id, **item) for item in raw_items]

