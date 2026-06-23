from __future__ import annotations

from pathlib import Path

from agentlens.config import load_config, load_settings
from agentlens.episodes import build_review_episodes
from agentlens.intelligence import IntelligenceLayer
from agentlens.policy import PolicyEngine
from agentlens.risk import SemanticRiskClassifier
from agentlens.schemas import (
    DecisionContext,
    DependencyEvidence,
    ExplainMoreResponse,
    Gate,
    GateQuestionResponse,
    GateStatus,
    PolicyAction,
    PolicyDecision,
    RiskAssessment,
    Session,
    SessionGoalSummary,
    SessionStart,
    Timeline,
    ToolCallProposal,
    TraceEvent,
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
        context = self._decision_context(proposal, event, risk, policy)
        if policy.action == PolicyAction.AUTO_EXECUTE:
            card = self.intelligence.fallback_card(
                proposal,
                risk,
                trajectory_preview="No trajectory generated because policy auto-executed this low-risk action.",
            )
            card.dependency_evidence = context.dependency_evidence
        elif self._uses_fast_intelligence(proposal):
            card = self.intelligence.fallback_card(
                proposal,
                risk,
                trajectory_preview=(
                    "Fast hook mirror mode recorded this action without running the full "
                    "OpenAI trajectory pipeline."
                ),
            )
            card.dependency_evidence = context.dependency_evidence
            card.model_roles = {"summary": "deterministic_fast_hook"}
        else:
            card = self.intelligence.build_card(context)

        status = GateStatus.PENDING
        if self._is_passive_observation(proposal):
            status = GateStatus.AUTO_EXECUTED
        elif policy.action == PolicyAction.AUTO_EXECUTE:
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
        return Timeline(
            session=self.session,
            traces=traces,
            gates=gates,
            episodes=build_review_episodes(session=self.session, traces=traces, gates=gates),
        )

    def explain(self, gate_id: str) -> ExplainMoreResponse:
        gate = self.storage.gates.get(gate_id)
        if gate is None or gate.session_id != self.session.id:
            raise KeyError(gate_id)
        card = gate.intelligence_card
        dependency_evidence = card.dependency_evidence if card else []
        confidence_evidence = card.confidence_evidence if card else []
        suggested_modification = None
        if gate.status == GateStatus.PENDING:
            suggested_modification = self._suggested_modification(gate)
        return ExplainMoreResponse(
            gate_id=gate.id,
            summary=card.summary if card else None,
            risk=gate.risk_assessment,
            policy=gate.policy_decision,
            trajectory=card.full_trajectory if card else None,
            drift_flag=card.drift_flag if card else None,
            confidence=card.confidence if card else None,
            confidence_evidence=confidence_evidence,
            dependency_evidence=dependency_evidence,
            suggested_modification=suggested_modification,
            context_summary=self._session_summary(),
        )

    def answer_question(self, gate_id: str, question: str) -> GateQuestionResponse:
        gate = self.storage.gates.get(gate_id)
        if gate is None or gate.session_id != self.session.id:
            raise KeyError(gate_id)
        trace = self._trace_for_gate(gate)
        proposal = ToolCallProposal(
            id=gate.proposal_id,
            session_id=gate.session_id,
            tool_name=trace.tool_name if trace else "unknown",
            params=trace.params if trace else {},
            stated_reason=trace.stated_reason if trace else None,
            confidence=gate.intelligence_card.confidence if gate.intelligence_card else None,
            provider_metadata={"source": "stored_trace"},
        )
        event = trace or self.trace_engine.capture(proposal, self.session.repo_path)
        context = self._decision_context(proposal, event, gate.risk_assessment, gate.policy_decision)
        if gate.intelligence_card:
            context.dependency_evidence = gate.intelligence_card.dependency_evidence
        result = self.intelligence.answer_gate_question(
            question=question,
            context=context,
            gate_summary=gate.intelligence_card.summary if gate.intelligence_card else None,
        )
        result.gate_id = gate.id
        return result

    def _decision_context(
        self,
        proposal: ToolCallProposal,
        event: TraceEvent,
        risk: RiskAssessment,
        policy: PolicyDecision,
    ) -> DecisionContext:
        traces, gates = self.storage.timeline(self.session.id)
        dependency_records = self.risk_classifier.dependency_evidence_for_paths(risk.affected_files)
        dependency_evidence = [
            DependencyEvidence(path=path, **record)
            for path, record in dependency_records.items()
        ]
        recent_actions = [
            f"{trace.tool_name} {trace.params}" for trace in (traces + [event])[-8:]
        ]
        recent_gate_payloads = [
            {
                "status": gate.status,
                "risk_level": gate.risk_assessment.risk_level,
                "policy_action": gate.policy_decision.action,
                "summary": gate.intelligence_card.summary if gate.intelligence_card else None,
            }
            for gate in gates[-6:]
        ]
        goal = SessionGoalSummary(
            inferred_goal=self.session.original_instruction,
            recent_actions=recent_actions,
            open_questions=self._open_questions(risk, policy),
        )
        return DecisionContext(
            session_id=self.session.id,
            original_instruction=self.session.original_instruction,
            proposal=proposal,
            risk=risk,
            policy=policy,
            recent_traces=(traces + [event])[-8:],
            recent_gates=recent_gate_payloads,
            git_snapshot=event.git_snapshot,
            dependency_evidence=dependency_evidence,
            session_goal=goal,
            visible_metadata={
                "trace_id": event.id,
                "session_created_at": self.session.created_at.isoformat(),
            },
        )

    def _session_summary(self) -> str:
        traces, gates = self.storage.timeline(self.session.id)
        trace_lines = [
            f"{event.tool_name} {event.params} reason={event.stated_reason or 'not provided'}"
            for event in traces[-8:]
        ]
        gate_lines = [
            f"{gate.status} risk={gate.risk_assessment.risk_level} policy={gate.policy_decision.action}"
            for gate in gates[-8:]
        ]
        return "\n".join(trace_lines + gate_lines) or "No prior session activity."

    def _open_questions(self, risk: RiskAssessment, policy: PolicyDecision) -> list[str]:
        questions: list[str] = []
        if policy.action != PolicyAction.AUTO_EXECUTE:
            questions.append("Should this action be approved before execution?")
        if risk.affected_files:
            questions.append("Have referenced callers and configuration links been checked?")
        if risk.risk_level in {"high", "critical"}:
            questions.append("Is there a safer scoped alternative?")
        return questions

    def _suggested_modification(self, gate: Gate) -> str:
        files = ", ".join(gate.risk_assessment.affected_files[:3])
        if gate.risk_assessment.risk_level == "critical":
            return "Do not execute the destructive action; inspect references and propose a reversible migration plan first."
        if files:
            return f"Inspect references for {files}, then propose the smallest reversible change."
        return "Ask the agent to restate the intended effect and provide a lower-risk command or patch."

    def _trace_for_gate(self, gate: Gate) -> TraceEvent | None:
        traces, _ = self.storage.timeline(gate.session_id)
        return next((trace for trace in traces if trace.proposal_id == gate.proposal_id), None)

    def _uses_fast_intelligence(self, proposal: ToolCallProposal) -> bool:
        return (
            proposal.provider_metadata.get("fast_intelligence") is True
            or proposal.provider_metadata.get("source") == "codex_hook"
            or self._is_passive_observation(proposal)
        )

    def _is_passive_observation(self, proposal: ToolCallProposal) -> bool:
        return proposal.provider_metadata.get("passive") is True
