from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentlens.schemas import PolicyAction, RiskLevel, ToolCallProposal

PATH_MATCH_KEYS = {
    "path",
    "paths",
    "affected_files",
    "affectedFiles",
    "file",
    "files",
    "file_path",
    "filePath",
    "relativePath",
    "target",
    "targets",
    "grant_root",
    "grantRoot",
    "command",
    "cmd",
    "query",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    openai_nano_model: str = "gpt-4.1-nano"
    openai_embedding_model: str = "text-embedding-3-small"
    database_url: str = "postgresql+asyncpg://agentlens:agentlens@localhost:5432/agentlens"
    redis_url: str = "redis://localhost:6379/0"
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_channel_id: str = ""
    agentlens_audit_log_path: str = "local_data/agentlens_audit.jsonl"
    agentlens_storage_backend: Literal["memory", "local_jsonl", "postgres"] = "memory"
    agentlens_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key != "replace_me")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.agentlens_cors_origins.split(",") if origin.strip()]


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
            fragments = [str(fragment).lower() for fragment in condition["path_contains"]]
            targets = [value.lower() for value in _policy_target_strings(proposal)]
            if not any(fragment in target for fragment in fragments for target in targets):
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


def _policy_target_strings(proposal: ToolCallProposal) -> list[str]:
    values: list[str] = []
    _collect_matching_strings(proposal.params, PATH_MATCH_KEYS, values)
    raw_request = proposal.provider_metadata.get("raw_request")
    _collect_matching_strings(raw_request, PATH_MATCH_KEYS, values)
    if proposal.stated_reason:
        values.append(proposal.stated_reason)
    return _unique_strings(values)


def _collect_matching_strings(value: Any, keys: set[str], output: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                _collect_all_strings(item, output)
            else:
                _collect_matching_strings(item, keys, output)
        return
    if isinstance(value, list):
        for item in value:
            _collect_matching_strings(item, keys, output)


def _collect_all_strings(value: Any, output: list[str]) -> None:
    if isinstance(value, str) and value.strip():
        output.append(value.strip())
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_all_strings(item, output)
        return
    if isinstance(value, list):
        for item in value:
            _collect_all_strings(item, output)


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


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


def save_config(config_path: str | os.PathLike[str], config: AgentLensConfig) -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="json", exclude_none=True)
    rendered = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)
