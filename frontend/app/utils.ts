import type { CountBucket, Gate, HealthState, LedgerAnalytics, ReviewEpisode, RiskLevel, SessionSummary, TraceEvent } from "./types";

export const riskDot: Record<RiskLevel, string> = {
  low: "bg-emerald-500",
  medium: "bg-amber-500",
  high: "bg-orange-600",
  critical: "bg-red-600",
};

export const riskChip: Record<RiskLevel, string> = {
  low: "border-emerald-200 bg-emerald-50 text-emerald-800",
  medium: "border-amber-200 bg-amber-50 text-amber-900",
  high: "border-orange-200 bg-orange-50 text-orange-900",
  critical: "border-red-200 bg-red-50 text-red-800",
};

export const statusChip = {
  pending: "border-sky-200 bg-sky-50 text-sky-800",
  approved: "border-emerald-200 bg-emerald-50 text-emerald-800",
  blocked: "border-red-200 bg-red-50 text-red-800",
  modified: "border-violet-200 bg-violet-50 text-violet-800",
  auto_executed: "border-neutral-200 bg-neutral-100 text-neutral-700",
};

export function titleCase(value: string) {
  return value
    .replace(/[_.]/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function toolLabel(value: string | undefined) {
  const labels: Record<string, string> = {
    "fs.read": "File Read",
    "fs.write": "File Write",
    "fs.delete": "File Delete",
    "shell.run": "Shell Command",
    "db.query": "Database Query",
    "api.call": "API Call",
    git_status: "Git Status",
    run_tests: "Run Tests",
  };
  return value ? (labels[value] ?? titleCase(value)) : "Tool Call";
}

export function healthLabel(health: HealthState) {
  if (health === "online") return "Backend Online";
  if (health === "offline") return "Backend Offline";
  return "Checking Backend";
}

export function sessionLabel(session: SessionSummary) {
  const id = session.id.slice(0, 12);
  const instruction = session.original_instruction.replace(/\s+/g, " ").trim();
  return `${id} / ${instruction.slice(0, 54) || "Untitled session"}`;
}

export function isLocalApi(apiUrl: string) {
  return /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?/.test(apiUrl);
}

export function isInspectionGate(gate: Gate, trace: TraceEvent | undefined) {
  if (gate.status !== "auto_executed") return false;
  if (gate.risk_assessment.risk_level !== "low") return false;
  const tool = trace?.tool_name ?? "";
  if (tool === "fs.read" || tool === "git.status" || tool === "run_tests") return true;
  if (tool !== "shell.run") return false;
  return isReadOnlyCommand(String(trace?.params.command ?? trace?.params.cmd ?? ""));
}

export function isInspectionTrace(trace: TraceEvent) {
  if (trace.tool_name === "fs.read" || trace.tool_name === "git.status") return true;
  if (trace.tool_name !== "shell.run") return false;
  return isReadOnlyCommand(String(trace.params.command ?? trace.params.cmd ?? ""));
}

function isReadOnlyCommand(command: string) {
  const lower = command.toLowerCase();
  return [
    "pwd",
    "ls",
    "rg",
    "grep",
    "find",
    "cat",
    "sed",
    "head",
    "tail",
    "git status",
    "git diff",
    "git show",
    "tree",
    "wc",
  ].some((hint) => lower.includes(hint));
}

export function summarizeTrace(trace: TraceEvent) {
  if (trace.tool_name === "shell.run") {
    return String(trace.params.command ?? trace.params.cmd ?? "Shell command captured.");
  }
  if (trace.params.path) return String(trace.params.path);
  return "Tool call captured.";
}

export function gateTarget(gate: Gate, trace?: TraceEvent) {
  return (
    gate.risk_assessment.affected_files[0]
    ?? (typeof trace?.params.path === "string" ? trace.params.path : null)
    ?? (typeof trace?.params.command === "string" ? "External command" : null)
    ?? "External state"
  );
}

export function episodePrimaryGate(episode: ReviewEpisode, gates: Gate[]) {
  return (
    gates.find((gate) => gate.id === episode.primary_gate_id)
    ?? gates.find((gate) => episode.gate_ids.includes(gate.id))
    ?? null
  );
}

export function episodeTraceCount(episode: ReviewEpisode) {
  return episode.counts.traces ?? episode.trace_ids.length;
}

export function buildFallbackEpisodes(
  gates: Gate[],
  traces: TraceEvent[],
  traceByProposal: Map<string, TraceEvent>,
): ReviewEpisode[] {
  const gateByProposal = new Map(gates.map((gate) => [gate.proposal_id, gate]));
  const handled = new Set<string>();
  const episodes: ReviewEpisode[] = [];
  const inspectionTraceIds: string[] = [];
  const inspectionGateIds: string[] = [];

  traces.forEach((trace) => {
    const gate = gateByProposal.get(trace.proposal_id);
    if (gate) handled.add(gate.id);
    if (gate && isInspectionGate(gate, trace)) {
      inspectionTraceIds.push(trace.id);
      inspectionGateIds.push(gate.id);
      return;
    }
    if (!gate) {
      episodes.push(fallbackTraceEpisode(trace, episodes.length));
      return;
    }
    episodes.push(fallbackGateEpisode(gate, trace, episodes.length));
  });

  gates.forEach((gate) => {
    if (handled.has(gate.id)) return;
    const trace = traceByProposal.get(gate.proposal_id);
    if (isInspectionGate(gate, trace)) {
      if (trace) inspectionTraceIds.push(trace.id);
      inspectionGateIds.push(gate.id);
      return;
    }
    episodes.push(fallbackGateEpisode(gate, trace, episodes.length));
  });

  if (inspectionTraceIds.length || inspectionGateIds.length) {
    episodes.unshift({
      id: "epi_fallback_inspections",
      session_id: gates[0]?.session_id ?? "",
      prompt: "",
      kind: "inspection_batch",
      status: "auto_executed",
      risk_level: "low",
      confidence: null,
      primary_gate_id: inspectionGateIds[0] ?? null,
      trace_ids: inspectionTraceIds,
      gate_ids: inspectionGateIds,
      descriptor: {
        human_title: "Inspected repository context",
        plain_action: "gathering context",
        target_label: "repository context",
        technical_detail: "read-only inspection",
        raw_detail: null,
        evidence_summary: "read-only shell/file inspection calls",
      },
      summary: `${inspectionTraceIds.length || inspectionGateIds.length} read-only shell/file inspection calls collapsed.`,
      counts: { traces: inspectionTraceIds.length, gates: inspectionGateIds.length },
    });
  }
  return episodes;
}

function fallbackGateEpisode(gate: Gate, trace: TraceEvent | undefined, index: number): ReviewEpisode {
  const target = gateTarget(gate, trace);
  return {
    id: `epi_fallback_${gate.id}`,
    session_id: gate.session_id,
    prompt: "",
    kind: "decision",
    status: gate.status,
    risk_level: gate.risk_assessment.risk_level,
    confidence: gate.intelligence_card?.confidence ?? null,
    primary_gate_id: gate.id,
    trace_ids: trace ? [trace.id] : [],
    gate_ids: [gate.id],
    descriptor: {
      human_title: `${toolLabel(trace?.tool_name)} on ${target}`,
      plain_action: `${toolLabel(trace?.tool_name).toLowerCase()} on ${target}`,
      target_label: target,
      technical_detail: trace?.tool_name ?? null,
      raw_detail: trace ? summarizeTrace(trace) : null,
      evidence_summary: gate.risk_assessment.evidence[0] ?? gate.policy_decision.reason,
    },
    summary: gate.intelligence_card?.summary ?? gate.policy_decision.reason,
    counts: { traces: trace ? 1 : 0, gates: 1 },
    created_at: gate.created_at,
    updated_at: gate.resolved_at ?? gate.created_at,
  };
}

function fallbackTraceEpisode(trace: TraceEvent, index: number): ReviewEpisode {
  const target = summarizeTrace(trace);
  return {
    id: `epi_fallback_trace_${trace.id}`,
    session_id: "",
    prompt: "",
    kind: "observation_batch",
    status: "auto_executed",
    risk_level: "low",
    confidence: null,
    primary_gate_id: null,
    trace_ids: [trace.id],
    gate_ids: [],
    descriptor: {
      human_title: `${toolLabel(trace.tool_name)} observed`,
      plain_action: `observing ${target}`,
      target_label: target,
      technical_detail: trace.tool_name,
      raw_detail: target,
      evidence_summary: trace.stated_reason ?? "captured tool metadata",
    },
    summary: trace.stated_reason ?? target,
    counts: { traces: 1, gates: 0 },
    created_at: trace.created_at,
    updated_at: trace.created_at,
  };
}

export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `${Math.round(value * 100)}%`;
}

export function shortId(id: string) {
  return id.slice(0, 13);
}

export function analyticsWithGateFallback(
  analytics: LedgerAnalytics | null,
  gates: Gate[],
  sessionId: string | null,
) {
  if (!gates.length) return analytics;
  if (analytics && analytics.trust_score.total_actions > 0) return analytics;
  return buildAnalyticsFromGates(gates, sessionId ?? analytics?.session_id ?? "local-session");
}

function buildAnalyticsFromGates(gates: Gate[], sessionId: string): LedgerAnalytics {
  const totalActions = gates.length;
  const autoExecuted = gates.filter((gate) => gate.status === "auto_executed").length;
  const humanInterventions = totalActions - autoExecuted;
  return {
    session_id: sessionId,
    trust_score: {
      score: totalActions ? autoExecuted / totalActions : 0,
      auto_executed: autoExecuted,
      human_interventions: humanInterventions,
      total_actions: totalActions,
    },
    approval_patterns: countBuckets(gates.map((gate) => gate.status)),
    risk_distribution: countBuckets(gates.map((gate) => gate.risk_assessment.risk_level)),
    drift_history: gates
      .filter((gate) => gate.intelligence_card?.drift_flag)
      .map((gate) => ({
        gate_id: gate.id,
        risk_level: gate.risk_assessment.risk_level,
        status: gate.status,
        drift_flag: gate.intelligence_card?.drift_flag ?? "",
      })),
  };
}

function countBuckets(values: string[]): CountBucket[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([name, count]) => ({ name, count }));
}
