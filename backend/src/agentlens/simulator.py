from __future__ import annotations

from collections.abc import Iterable

from agentlens.schemas import ToolCallProposal
from agentlens.session import AgentLensSession


class ToolCallSimulator:
    def __init__(self, session: AgentLensSession) -> None:
        self.session = session

    def replay(self, proposals: Iterable[dict]) -> list:
        gates = []
        for raw in proposals:
            proposal = ToolCallProposal(session_id=self.session.session.id, **raw)
            gate = self.session.propose(proposal)
            gates.append(gate)
            if gate.status == "blocked":
                break
        return gates


def default_demo_proposals(session_id: str) -> list[ToolCallProposal]:
    return [
        ToolCallProposal(
            session_id=session_id,
            tool_name="fs.read",
            params={"path": "prd.md"},
            stated_reason="Need to inspect product requirements.",
            confidence=0.95,
        ),
        ToolCallProposal(
            session_id=session_id,
            tool_name="fs.delete",
            params={"path": "backend/migrations/001_sessions.py"},
            stated_reason="Migration appears redundant.",
            confidence=0.58,
        ),
    ]

