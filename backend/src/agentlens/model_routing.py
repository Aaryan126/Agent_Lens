from __future__ import annotations

from agentlens.config import Settings
from agentlens.schemas import ModelRole, PolicyAction, RiskLevel, ToolCallProposal


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def model_for(self, role: ModelRole) -> str:
        if role == ModelRole.NANO:
            return self.settings.openai_nano_model
        if role == ModelRole.EMBEDDING:
            return self.settings.openai_embedding_model
        return self.settings.openai_model

    def role_for_intelligence(
        self, proposal: ToolCallProposal, risk_level: RiskLevel, policy_action: PolicyAction
    ) -> ModelRole:
        if policy_action != PolicyAction.AUTO_EXECUTE:
            return ModelRole.STRONG
        if risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return ModelRole.STRONG
        if proposal.tool_name in {"fs.write", "fs.delete", "api.call", "db.query"}:
            return ModelRole.STRONG
        if proposal.tool_name == "shell.run":
            return ModelRole.STRONG
        return ModelRole.NANO

    def role_for_summary(self, risk_level: RiskLevel) -> ModelRole:
        if risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return ModelRole.STRONG
        return ModelRole.NANO
