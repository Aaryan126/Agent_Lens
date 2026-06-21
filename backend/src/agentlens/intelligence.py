from __future__ import annotations

import math
import os

from openai import OpenAI

from agentlens.config import Settings
from agentlens.schemas import (
    ConfidenceAssessment,
    DriftAssessment,
    IntelligenceCard,
    RiskAssessment,
    ToolCallProposal,
    TrajectoryPrediction,
    TrajectoryStep,
    TranslationResult,
)


class IntelligenceLayer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
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
        )

    def build_card(
        self,
        instruction: str,
        proposal: ToolCallProposal,
        risk: RiskAssessment,
        session_summary: str,
    ) -> IntelligenceCard:
        if not self.settings.has_openai_key:
            return self.fallback_card(proposal, risk)

        trajectory = self.trajectory(instruction, proposal)
        action_intent = proposal.stated_reason or f"Run {proposal.tool_name} with {proposal.params}"
        drift = self.drift(instruction, session_summary, action_intent)
        confidence = self.confidence(proposal, risk)
        translation = self.translation(proposal, risk, trajectory, drift, confidence)

        first_step = trajectory.next_steps[0].action if trajectory.next_steps else "No likely next step"
        drift_flag = drift.explanation if drift.drift_detected else None
        return IntelligenceCard(
            proposal_id=proposal.id,
            summary=translation.summary,
            risk_badge=risk.risk_level,
            confidence=confidence.score,
            trajectory_preview=(
                f"If approved, next likely action: {first_step}. "
                f"Commitment point: {trajectory.commitment_point}."
            ),
            drift_flag=drift_flag,
        )

    def trajectory(self, instruction: str, proposal: ToolCallProposal) -> TrajectoryPrediction:
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
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": "Predict the next three likely agent steps as strict JSON.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Original instruction: {instruction}\n"
                        f"Tool: {proposal.tool_name}\nParams: {proposal.params}\n"
                        f"Reason: {proposal.stated_reason}"
                    ),
                },
            ],
            text_format=TrajectoryPrediction,
        )
        return response.output_parsed

    def drift(self, instruction: str, session_summary: str, action_intent: str) -> DriftAssessment:
        if not self.settings.has_openai_key:
            return DriftAssessment(
                drift_detected=False,
                score=0.5,
                explanation="OpenAI credentials are not configured; drift check used neutral fallback.",
            )

        original_embedding, current_embedding = self._embed_pair(
            instruction, f"{session_summary}\nCurrent action intent: {action_intent}"
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
        evidence = ["used provider confidence when available"]
        if risk.risk_level in {"high", "critical"}:
            base = min(base, 0.7)
            evidence.append("capped confidence for high-risk action")
        return ConfidenceAssessment(score=base, evidence=evidence)

    def translation(
        self,
        proposal: ToolCallProposal,
        risk: RiskAssessment,
        trajectory: TrajectoryPrediction,
        drift: DriftAssessment,
        confidence: ConfidenceAssessment,
    ) -> TranslationResult:
        if not self.settings.has_openai_key:
            return TranslationResult(summary=self.fallback_card(proposal, risk).summary)

        response = self.client.responses.parse(
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Write an approval-card summary for a developer who has not watched "
                        "the session. Return exactly one JSON object. The summary must be at "
                        "most two concise sentences and include action, reason, codebase "
                        "evidence, risk, and confidence."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Tool: {proposal.tool_name}\n"
                        f"Params: {proposal.params}\n"
                        f"Agent stated reason: {proposal.stated_reason}\n"
                        f"Risk: {risk.risk_level}\n"
                        f"Reversibility: {risk.reversibility}\n"
                        f"Blast radius: {risk.blast_radius}\n"
                        f"Evidence: {risk.evidence}\n"
                        f"Trajectory: {trajectory.model_dump()}\n"
                        f"Drift: {drift.model_dump()}\n"
                        f"Confidence: {confidence.model_dump()}"
                    ),
                },
            ],
            text_format=TranslationResult,
        )
        return response.output_parsed

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
