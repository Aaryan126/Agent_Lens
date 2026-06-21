from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentlens.schemas import PolicyAction, RiskLevel, ToolCallProposal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    openai_embedding_model: str = "text-embedding-3-small"
    database_url: str = "postgresql+asyncpg://agentlens:agentlens@localhost:5432/agentlens"
    redis_url: str = "redis://localhost:6379/0"
    slack_bot_token: str = ""
    slack_signing_secret: str = ""

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key != "replace_me")


class PolicyRule(BaseModel):
    name: str
    condition: dict[str, Any] = Field(default_factory=dict)
    action: PolicyAction
    min_confidence: float | None = None

    def matches(self, proposal: ToolCallProposal, risk_level: RiskLevel | None = None) -> bool:
        condition = self.condition
        if "tool_in" in condition and proposal.tool_name not in set(condition["tool_in"]):
            return False

        if "path_contains" in condition:
            path = str(proposal.params.get("path", ""))
            if not any(fragment in path for fragment in condition["path_contains"]):
                return False

        if "param_contains" in condition:
            for key, fragments in condition["param_contains"].items():
                value = str(proposal.params.get(key, "")).lower()
                if not any(fragment.lower() in value for fragment in fragments):
                    return False

        if "confidence_below" in condition:
            confidence = proposal.confidence
            if confidence is None or confidence >= float(condition["confidence_below"]):
                return False

        if "risk_not" in condition and risk_level is not None:
            if risk_level == condition["risk_not"]:
                return False

        return True


class AgentLensConfig(BaseModel):
    policies: list[PolicyRule] = Field(default_factory=list)


def load_settings() -> Settings:
    return Settings()


def load_config(config_path: str | os.PathLike[str]) -> AgentLensConfig:
    path = Path(config_path)
    if not path.exists():
        return AgentLensConfig()
    raw = yaml.safe_load(path.read_text()) or {}
    return AgentLensConfig.model_validate(raw)

