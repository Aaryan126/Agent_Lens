from __future__ import annotations

from pathlib import Path

from agentlens.config import load_config, load_settings
from agentlens.intelligence import IntelligenceLayer
from agentlens.policy import PolicyEngine
from agentlens.risk import SemanticRiskClassifier
from agentlens.schemas import (
    Gate,
    GateStatus,
    PolicyAction,
    Session,
    SessionStart,
    Timeline,
    ToolCallProposal,
)
from agentlens.storage import InMemoryStore, store
from agentlens.trace import TraceEngine


class AgentLensSession:
    def __init__(self, session: Session, storage: InMemoryStore = store) -> None:
        self.session = session
        self.storage = storage
        self.trace_engine = TraceEngine()
        self.risk_classifier = SemanticRiskClassifier(session.repo_path)
        self.policy_engine = PolicyEngine(load_config(Path(session.repo_path) / session.config_path))
        self.intelligence = IntelligenceLayer(load_settings())

    @classmethod
    def start(
        cls, payload: SessionStart, storage: InMemoryStore = store
    ) -> "AgentLensSession":
        session = Session(**payload.model_dump())
        storage.add_session(session)
        return cls(session, storage=storage)

    def propose(self, proposal: ToolCallProposal) -> Gate:
        event = self.trace_engine.capture(proposal, self.session.repo_path)
        self.storage.add_trace(event)

        risk = self.risk_classifier.assess(proposal)
        policy = self.policy_engine.evaluate(proposal, risk)
        card = self.intelligence.fallback_card(proposal, risk)

        status = GateStatus.PENDING
        if policy.action == PolicyAction.AUTO_EXECUTE:
            status = GateStatus.AUTO_EXECUTED
        elif policy.action == PolicyAction.BLOCK_AND_ALERT:
            status = GateStatus.BLOCKED

        gate = Gate(
            session_id=self.session.id,
            proposal_id=proposal.id,
            status=status,
            policy_decision=policy,
            risk_assessment=risk,
            intelligence_card=card,
        )
        self.storage.add_gate(gate)
        return gate

    def timeline(self) -> Timeline:
        traces, gates = self.storage.timeline(self.session.id)
        return Timeline(session=self.session, traces=traces, gates=gates)

