from __future__ import annotations

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
)


class IntelligenceLayer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key or os.getenv("OPENAI_API_KEY"))

    def fallback_card(self, proposal: ToolCallProposal, risk: RiskAssessment) -> IntelligenceCard:
        summary = (
            f"Agent wants to run {proposal.tool_name} with risk {risk.risk_level}. "
            f"Evidence: {risk.evidence[0] if risk.evidence else 'no evidence available'}."
        )
        return IntelligenceCard(
            proposal_id=proposal.id,
            summary=summary[:280],
            risk_badge=risk.risk_level,
            confidence=proposal.confidence if proposal.confidence is not None else 0.5,
            trajectory_preview="Next action unknown until OpenAI intelligence is configured.",
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

        response = self.client.responses.parse(
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": "Assess whether the current action has drifted from the original task.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Original instruction: {instruction}\n"
                        f"Session summary: {session_summary}\n"
                        f"Current action intent: {action_intent}"
                    ),
                },
            ],
            text_format=DriftAssessment,
        )
        return response.output_parsed

    def confidence(self, proposal: ToolCallProposal, risk: RiskAssessment) -> ConfidenceAssessment:
        base = proposal.confidence if proposal.confidence is not None else 0.5
        evidence = ["used provider confidence when available"]
        if risk.risk_level in {"high", "critical"}:
            base = min(base, 0.7)
            evidence.append("capped confidence for high-risk action")
        return ConfidenceAssessment(score=base, evidence=evidence)

