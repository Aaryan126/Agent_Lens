import type { CountBucket, Gate, HealthState, LedgerAnalytics, RiskLevel, SessionSummary, TraceEvent } from "./types";

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
