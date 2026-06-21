from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class ToolName(StrEnum):
    FS_READ = "fs.read"
    FS_WRITE = "fs.write"
    FS_DELETE = "fs.delete"
    SHELL = "shell.run"
    API_CALL = "api.call"
    DB_QUERY = "db.query"
    GIT_STATUS = "git.status"
    RUN_TESTS = "run_tests"


class PolicyAction(StrEnum):
    AUTO_EXECUTE = "auto_execute"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK_AND_ALERT = "block_and_alert"


class GateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"
    MODIFIED = "modified"
    AUTO_EXECUTED = "auto_executed"


class Reversibility(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BlastRadius(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SessionStart(BaseModel):
    original_instruction: str
    repo_path: str = "."
    user_id: str = "local-user"
    team_id: str = "local-team"
    config_path: str = "agentlens.config.yaml"


class Session(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ses"))
    original_instruction: str
    repo_path: str
    user_id: str
    team_id: str
    config_path: str
    created_at: datetime = Field(default_factory=utc_now)


class ToolCallProposal(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tool"))
    session_id: str
    tool_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    stated_reason: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class GitSnapshot(BaseModel):
    status_short: str = ""
    diff: str = ""
    available: bool = True
    error: str | None = None


class TraceEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evt"))
    session_id: str
    proposal_id: str
    tool_name: str
    params: dict[str, Any]
    stated_reason: str | None = None
    git_snapshot: GitSnapshot = Field(default_factory=GitSnapshot)
    created_at: datetime = Field(default_factory=utc_now)


class RiskAssessment(BaseModel):
    proposal_id: str
    reversibility: Reversibility
    blast_radius: BlastRadius
    risk_level: RiskLevel
    recommended_action: PolicyAction
    evidence: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)


class PolicyDecision(BaseModel):
    proposal_id: str
    action: PolicyAction
    matched_policy: str | None = None
    reason: str


class TrajectoryStep(BaseModel):
    step: int
    action: str
    rationale: str


class TrajectoryPrediction(BaseModel):
    next_steps: list[TrajectoryStep] = Field(default_factory=list)
    commitment_point: str
    confidence: float = Field(ge=0.0, le=1.0)


class DriftAssessment(BaseModel):
    drift_detected: bool
    score: float = Field(ge=0.0, le=1.0)
    explanation: str


class ConfidenceAssessment(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class TranslationResult(BaseModel):
    summary: str = Field(max_length=500)


class IntelligenceCard(BaseModel):
    proposal_id: str
    summary: str
    risk_badge: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)
    trajectory_preview: str
    drift_flag: str | None = None


class Gate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("gate"))
    session_id: str
    proposal_id: str
    status: GateStatus = GateStatus.PENDING
    policy_decision: PolicyDecision
    risk_assessment: RiskAssessment
    intelligence_card: IntelligenceCard | None = None
    human_reason: str | None = None
    modified_instruction: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None


class Timeline(BaseModel):
    session: Session
    traces: list[TraceEvent]
    gates: list[Gate]
