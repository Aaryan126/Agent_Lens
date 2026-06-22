from __future__ import annotations

import math
import os

from openai import OpenAI

from agentlens.config import Settings
from agentlens.model_routing import ModelRouter
from agentlens.schemas import (
    ConfidenceAssessment,
    ConfidenceEvidence,
    DecisionContext,
    DriftAssessment,
    IntelligenceCard,
    ModelRole,
    PolicyAction,
    RiskAssessment,
    RiskLevel,
    ToolCallProposal,
    TrajectoryPrediction,
    TrajectoryStep,
    TranslationResult,
)


class IntelligenceLayer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.router = ModelRouter(settings)
        self.client = OpenAI(api_key=settings.openai_api_key or os.getenv("OPENAI_API_KEY"))

    def fallback_card(
        self,
        proposal: ToolCallProposal,
        risk: RiskAssessment,
        trajectory_preview: str | None = None,
    ) -> IntelligenceCard:
        summary = (
            f"Agent wants to run {proposal.tool_name} with risk {risk.risk_level}. "
            f"Evidence: {risk.evidence[0] if risk.evidence else 'no evidence available'}."
        )
        return IntelligenceCard(
            proposal_id=proposal.id,
            summary=summary[:280],
            risk_badge=risk.risk_level,
            confidence=proposal.confidence if proposal.confidence is not None else 0.5,
            trajectory_preview=trajectory_preview
            or "Next action unknown until OpenAI intelligence is configured.",
            confidence_evidence=self._confidence_factors(proposal, risk),
            dependency_evidence=[],
            model_roles={},
        )

    def build_card(self, context: DecisionContext) -> IntelligenceCard:
        proposal = context.proposal
        risk = context.risk
        if not self.settings.has_openai_key:
            card = self.fallback_card(proposal, risk)
            card.dependency_evidence = context.dependency_evidence
            return card

        intelligence_role = self.router.role_for_intelligence(
            proposal,
            risk.risk_level,
            context.policy.action,
        )
        translation_role = self.router.role_for_summary(risk.risk_level)

        trajectory = self.trajectory(context, role=intelligence_role)
        action_intent = proposal.stated_reason or f"Run {proposal.tool_name} with {proposal.params}"
        drift = self.drift(context, action_intent)
        confidence = self.confidence(proposal, risk)
        translation = self.translation(context, trajectory, drift, confidence, role=translation_role)

        first_step = trajectory.next_steps[0].action if trajectory.next_steps else "No likely next step"
        drift_flag = drift.explanation if drift.drift_detected else None
        return IntelligenceCard(
            proposal_id=proposal.id,
            summary=self._clean_summary(translation.summary),
            risk_badge=risk.risk_level,
            confidence=confidence.score,
            trajectory_preview=(
                f"If approved, next likely action: {first_step}. "
                f"Commitment point: {trajectory.commitment_point}."
            ),
            drift_flag=drift_flag,
            full_trajectory=trajectory,
            confidence_evidence=confidence.factors,
            dependency_evidence=context.dependency_evidence,
            drift_score=drift.score,
            model_roles={
                "trajectory": intelligence_role.value,
                "translation": translation_role.value,
                "drift": ModelRole.EMBEDDING.value,
            },
        )

    def trajectory(self, context: DecisionContext, *, role: ModelRole = ModelRole.STRONG) -> TrajectoryPrediction:
        if not self.settings.has_openai_key:
            return TrajectoryPrediction(
                next_steps=[
                    TrajectoryStep(
                        step=1,
                        action="Continue with the proposed tool call.",
                        rationale="Fallback prediction without OpenAI credentials.",
                    )
                ],
                commitment_point="current proposed action",
                confidence=0.35,
            )

        response = self.client.responses.parse(
            model=self.router.model_for(role),
            input=[
                {
                    "role": "system",
                    "content": (
                        "Predict the next three likely coding-agent steps as strict JSON. "
                        "Use only visible tool metadata, risk evidence, recent actions, and code "
                        "evidence. Do not reveal hidden chain-of-thought."
                    ),
                },
                {
                    "role": "user",
                    "content": self._context_prompt(context),
                },
            ],
            text_format=TrajectoryPrediction,
        )
        return response.output_parsed

    def drift(self, context: DecisionContext, action_intent: str) -> DriftAssessment:
        if not self.settings.has_openai_key:
            return DriftAssessment(
                drift_detected=False,
                score=0.5,
                explanation="OpenAI credentials are not configured; drift check used neutral fallback.",
            )

        original_embedding, current_embedding = self._embed_pair(
            context.original_instruction,
            (
                f"Inferred session goal: {context.session_goal.inferred_goal}\n"
                f"Recent actions: {context.session_goal.recent_actions}\n"
                f"Current action intent: {action_intent}\n"
                f"Risk evidence: {context.risk.evidence}"
            ),
        )
        similarity = self._cosine_similarity(original_embedding, current_embedding)
        drift_detected = similarity < 0.62
        if drift_detected:
            explanation = (
                "This action may be drifting from the original instruction; "
                f"embedding alignment is {similarity:.2f}."
            )
        else:
            explanation = f"Current action remains aligned with the original instruction ({similarity:.2f})."
        return DriftAssessment(
            drift_detected=drift_detected,
            score=max(0.0, min(1.0, similarity)),
            explanation=explanation,
        )

    def confidence(self, proposal: ToolCallProposal, risk: RiskAssessment) -> ConfidenceAssessment:
        base = proposal.confidence if proposal.confidence is not None else 0.5
        factors = self._confidence_factors(proposal, risk)
        for factor in factors:
            base += factor.impact
        if risk.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            base = min(base, 0.7)
        base = max(0.05, min(0.98, base))
        return ConfidenceAssessment(
            score=base,
            evidence=[factor.detail for factor in factors],
            factors=factors,
        )

    def translation(
        self,
        context: DecisionContext,
        trajectory: TrajectoryPrediction,
        drift: DriftAssessment,
        confidence: ConfidenceAssessment,
        *,
        role: ModelRole = ModelRole.NANO,
    ) -> TranslationResult:
        proposal = context.proposal
        risk = context.risk
        if not self.settings.has_openai_key:
            return TranslationResult(summary=self.fallback_card(proposal, risk).summary)

        response = self.client.responses.parse(
            model=self.router.model_for(role),
            input=[
                {
                    "role": "system",
                    "content": (
                        "Write an approval-card summary for a developer who has not watched "
                        "the session. Return exactly one JSON object. The summary must be at "
                        "most two concise sentences and include action, reason, codebase "
                        "evidence, risk, and confidence. Use English only and plain ASCII text."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{self._context_prompt(context)}\n"
                        f"Trajectory: {trajectory.model_dump()}\n"
                        f"Drift: {drift.model_dump()}\n"
                        f"Confidence: {confidence.model_dump()}"
                    ),
                },
            ],
            text_format=TranslationResult,
        )
        return response.output_parsed

    def _context_prompt(self, context: DecisionContext) -> str:
        proposal = context.proposal
        recent_traces = [
            {
                "tool": trace.tool_name,
                "params": trace.params,
                "reason": trace.stated_reason,
            }
            for trace in context.recent_traces[-6:]
        ]
        return (
            f"Original instruction: {context.original_instruction}\n"
            f"Inferred goal: {context.session_goal.inferred_goal}\n"
            f"Recent actions: {recent_traces}\n"
            f"Tool: {proposal.tool_name}\n"
            f"Params: {proposal.params}\n"
            f"Agent stated reason: {proposal.stated_reason}\n"
            f"Risk: {context.risk.risk_level}\n"
            f"Reversibility: {context.risk.reversibility}\n"
            f"Blast radius: {context.risk.blast_radius}\n"
            f"Risk evidence: {context.risk.evidence}\n"
            f"Dependency evidence: {[item.model_dump() for item in context.dependency_evidence]}\n"
            f"Policy action: {context.policy.action}\n"
            f"Policy reason: {context.policy.reason}\n"
            f"Git status: {context.git_snapshot.status_short[:1200]}\n"
            f"Git diff excerpt: {context.git_snapshot.diff[:2400]}"
        )

    def _confidence_factors(
        self, proposal: ToolCallProposal, risk: RiskAssessment
    ) -> list[ConfidenceEvidence]:
        factors: list[ConfidenceEvidence] = []
        if proposal.confidence is None:
            factors.append(
                ConfidenceEvidence(
                    label="Provider Confidence Missing",
                    impact=-0.1,
                    detail="The source event did not include a calibrated provider confidence.",
                )
            )
        else:
            factors.append(
                ConfidenceEvidence(
                    label="Provider Confidence Present",
                    impact=0.05,
                    detail=f"The source event reported {proposal.confidence:.0%} confidence.",
                )
            )
        if risk.affected_files:
            factors.append(
                ConfidenceEvidence(
                    label="Concrete Files Detected",
                    impact=0.08,
                    detail=f"AgentLens identified {len(risk.affected_files)} affected file path(s).",
                )
            )
        else:
            factors.append(
                ConfidenceEvidence(
                    label="No File Target",
                    impact=-0.05,
                    detail="The action has no clear affected file, so blast radius is less certain.",
                )
            )
        if risk.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            factors.append(
                ConfidenceEvidence(
                    label="High Consequence Cap",
                    impact=-0.12,
                    detail="Confidence is capped for high-risk or critical actions.",
                )
            )
        if risk.recommended_action == PolicyAction.AUTO_EXECUTE:
            factors.append(
                ConfidenceEvidence(
                    label="Policy Alignment",
                    impact=0.07,
                    detail="Semantic risk and policy both allow automatic execution.",
                )
            )
        return factors

    def _clean_summary(self, summary: str) -> str:
        cleaned = summary.encode("ascii", errors="ignore").decode().strip()
        cleaned = " ".join(cleaned.split())
        if len(cleaned) > 500:
            cleaned = cleaned[:497].rstrip() + "..."
        if cleaned and cleaned[-1] not in ".!?":
            cleaned = f"{cleaned}."
        return cleaned

    def _embed_pair(self, left: str, right: str) -> tuple[list[float], list[float]]:
        response = self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=[left, right],
        )
        return response.data[0].embedding, response.data[1].embedding

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)
