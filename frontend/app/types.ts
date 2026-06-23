export type RiskLevel = "low" | "medium" | "high" | "critical";
export type GateStatus = "pending" | "approved" | "blocked" | "modified" | "auto_executed";
export type HealthState = "checking" | "online" | "offline";
export type View = "review" | "trajectory" | "policies" | "slack" | "audit";

export type IntelligenceCard = {
  summary: string;
  risk_badge: RiskLevel;
  confidence: number;
  trajectory_preview: string;
  drift_flag: string | null;
  full_trajectory: {
    next_steps: { step: number; action: string; rationale: string }[];
    commitment_point: string;
    confidence: number;
    rationale: string;
  } | null;
  confidence_evidence: { label: string; impact: number; detail: string }[];
  dependency_evidence: {
    path: string;
    referenced_by: string[];
    config_references: string[];
    exists: boolean | null;
    summary: string;
  }[];
  drift_score: number | null;
  model_roles: Record<string, string>;
};

export type PolicyDecision = {
  action: string;
  matched_policy: string | null;
  reason: string;
};

export type PolicyRule = {
  name: string;
  condition: Record<string, unknown>;
  action: "auto_execute" | "require_approval" | "block_and_alert";
  min_confidence: number | null;
  _localId?: string;
};

export type PolicyConfigResponse = {
  config_path: string;
  policies: PolicyRule[];
  supported_conditions: Record<string, string>;
  supported_actions: PolicyRule["action"][];
};

export type PolicyTestResponse = {
  decision: PolicyDecision;
};

export type RiskAssessment = {
  reversibility: string;
  blast_radius: string;
  risk_level: RiskLevel;
  recommended_action: string;
  evidence: string[];
  affected_files: string[];
};

export type Gate = {
  id: string;
  session_id: string;
  proposal_id: string;
  status: GateStatus;
  policy_decision: PolicyDecision;
  risk_assessment: RiskAssessment;
  intelligence_card: IntelligenceCard | null;
  human_reason: string | null;
  modified_instruction: string | null;
  created_at?: string;
  resolved_at?: string | null;
};

export type TraceEvent = {
  id: string;
  proposal_id: string;
  tool_name: string;
  params: Record<string, unknown>;
  stated_reason: string | null;
  created_at?: string;
};

export type SessionSummary = {
  id: string;
  original_instruction: string;
  created_at?: string;
};

export type DemoResponse = {
  session: SessionSummary;
  gates: Gate[];
  timeline: {
    traces: TraceEvent[];
    gates: Gate[];
  };
};

export type TimelineResponse = {
  session: SessionSummary;
  traces: TraceEvent[];
  gates: Gate[];
};

export type CountBucket = {
  name: string;
  count: number;
};

export type LedgerAnalytics = {
  session_id: string;
  trust_score: {
    score: number;
    auto_executed: number;
    human_interventions: number;
    total_actions: number;
  };
  approval_patterns: CountBucket[];
  risk_distribution: CountBucket[];
  drift_history: {
    gate_id: string;
    risk_level: RiskLevel;
    status: GateStatus;
    drift_flag: string;
  }[];
};

export type SlackSendResult = {
  session_id: string;
  posted: { gate_id: string; channel: string; ts: string }[];
};

export type ExplainMoreResponse = {
  gate_id: string;
  summary: string | null;
  risk: RiskAssessment;
  policy: PolicyDecision;
  trajectory: IntelligenceCard["full_trajectory"];
  drift_flag: string | null;
  confidence: number | null;
  confidence_evidence: IntelligenceCard["confidence_evidence"];
  dependency_evidence: IntelligenceCard["dependency_evidence"];
  suggested_modification: string | null;
  context_summary: string;
};

export type GateQuestionResponse = {
  gate_id: string;
  question: string;
  answer: string;
  evidence: string[];
  used_model_role: string;
};
