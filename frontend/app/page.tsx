"use client";

import { useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_AGENTLENS_API_URL ?? "http://127.0.0.1:8000";
const DEFAULT_SLACK_CHANNEL = "C0BBW328TEF";

type RiskLevel = "low" | "medium" | "high" | "critical";
type GateStatus = "pending" | "approved" | "blocked" | "modified" | "auto_executed";
type HealthState = "checking" | "online" | "offline";

type IntelligenceCard = {
  summary: string;
  risk_badge: RiskLevel;
  confidence: number;
  trajectory_preview: string;
  drift_flag: string | null;
};

type PolicyDecision = {
  action: string;
  matched_policy: string | null;
  reason: string;
};

type RiskAssessment = {
  reversibility: string;
  blast_radius: string;
  risk_level: RiskLevel;
  recommended_action: string;
  evidence: string[];
  affected_files: string[];
};

type Gate = {
  id: string;
  session_id: string;
  proposal_id: string;
  status: GateStatus;
  policy_decision: PolicyDecision;
  risk_assessment: RiskAssessment;
  intelligence_card: IntelligenceCard | null;
  human_reason: string | null;
  modified_instruction: string | null;
};

type TraceEvent = {
  id: string;
  proposal_id: string;
  tool_name: string;
  params: Record<string, unknown>;
  stated_reason: string | null;
};

type DemoResponse = {
  session: {
    id: string;
    original_instruction: string;
  };
  gates: Gate[];
  timeline: {
    traces: TraceEvent[];
    gates: Gate[];
  };
};

type CountBucket = {
  name: string;
  count: number;
};

type LedgerAnalytics = {
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

type SlackSendResult = {
  session_id: string;
  posted: { gate_id: string; channel: string; ts: string }[];
};

const riskStyles: Record<RiskLevel, string> = {
  low: "border-emerald-200 bg-emerald-50 text-emerald-800",
  medium: "border-amber-200 bg-amber-50 text-amber-900",
  high: "border-rose-200 bg-rose-50 text-rose-800",
  critical: "border-red-300 bg-red-100 text-red-950",
};

const statusStyles: Record<GateStatus, string> = {
  pending: "border-sky-200 bg-sky-50 text-sky-800",
  approved: "border-emerald-200 bg-emerald-50 text-emerald-800",
  blocked: "border-red-200 bg-red-50 text-red-800",
  modified: "border-violet-200 bg-violet-50 text-violet-800",
  auto_executed: "border-neutral-200 bg-neutral-100 text-neutral-700",
};

export default function Home() {
  const [demo, setDemo] = useState<DemoResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [slackLoading, setSlackLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionNote, setDecisionNote] = useState("Reviewed from hosted AgentLens console.");
  const [analytics, setAnalytics] = useState<LedgerAnalytics | null>(null);
  const [health, setHealth] = useState<HealthState>("checking");
  const [slackChannel, setSlackChannel] = useState(DEFAULT_SLACK_CHANNEL);
  const [slackResult, setSlackResult] = useState<SlackSendResult | null>(null);

  useEffect(() => {
    let alive = true;
    fetch(`${API_URL}/health`)
      .then((response) => {
        if (alive) setHealth(response.ok ? "online" : "offline");
      })
      .catch(() => {
        if (alive) setHealth("offline");
      });
    return () => {
      alive = false;
    };
  }, []);

  const gates = demo?.timeline.gates ?? [];
  const traces = demo?.timeline.traces ?? [];
  const pendingCount = useMemo(
    () => gates.filter((gate) => gate.status === "pending").length,
    [gates],
  );
  const resolvedCount = useMemo(
    () =>
      gates.filter((gate) =>
        ["approved", "blocked", "modified", "auto_executed"].includes(gate.status),
      ).length,
    [gates],
  );
  const criticalCount = useMemo(
    () => gates.filter((gate) => gate.risk_assessment.risk_level === "critical").length,
    [gates],
  );
  const traceByProposal = useMemo(
    () => new Map(traces.map((trace) => [trace.proposal_id, trace])),
    [traces],
  );
  const apiHost = API_URL.replace(/^https?:\/\//, "");

  async function createDemo() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/demo/session`, { method: "POST" });
      if (!response.ok) throw new Error(`Demo failed with ${response.status}`);
      const nextDemo = (await response.json()) as DemoResponse;
      setDemo(nextDemo);
      setAnalytics(await fetchAnalytics(nextDemo.session.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create demo session");
    } finally {
      setLoading(false);
    }
  }

  async function sendSlackCards() {
    setSlackLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/demo/slack/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel_id: slackChannel }),
      });
      if (!response.ok) throw new Error(`Slack send failed with ${response.status}`);
      setSlackResult((await response.json()) as SlackSendResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to send Slack cards");
    } finally {
      setSlackLoading(false);
    }
  }

  async function decide(gate: Gate, action: "approve" | "block" | "modify") {
    setError(null);
    const payload =
      action === "modify"
        ? {
            reason: decisionNote,
            modified_instruction:
              "Continue, but inspect references and propose a safer scoped change first.",
          }
        : { reason: decisionNote };

    try {
      const response = await fetch(`${API_URL}/gates/${gate.id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(`Decision failed with ${response.status}`);
      const updated = (await response.json()) as Gate;
      setDemo((current) => {
        if (!current) return current;
        const updateGate = (item: Gate) => (item.id === updated.id ? updated : item);
        return {
          ...current,
          gates: current.gates.map(updateGate),
          timeline: {
            ...current.timeline,
            gates: current.timeline.gates.map(updateGate),
          },
        };
      });
      setAnalytics(await fetchAnalytics(updated.session_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit decision");
    }
  }

  return (
    <main className="min-h-screen bg-[#f3f3f1] text-neutral-950">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-5 pb-8 lg:px-8">
        <header className="-mx-5 grid gap-6 bg-neutral-950 px-5 py-6 text-white lg:-mx-8 lg:grid-cols-[minmax(0,1fr)_430px] lg:px-8">
          <div className="flex min-w-0 flex-col justify-between gap-6">
            <div className="flex flex-wrap items-center gap-2">
              <Pill label="AgentLens" tone="dark" />
              <Pill label="Hosted Demo" tone="blue" />
              <Pill label={healthLabel(health)} tone={health === "online" ? "green" : "amber"} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-neutral-400">
                AI Agent Supervision Console
              </p>
              <h1 className="mt-3 max-w-4xl text-4xl font-semibold leading-tight md:text-5xl">
                Review risky agent actions before they change production code.
              </h1>
            </div>
            <div className="grid gap-3 text-sm md:grid-cols-3">
              <ProofPoint label="Intelligence" value="Trajectory, drift, confidence" />
              <ProofPoint label="Approval Surface" value="Slack and console decisions" />
              <ProofPoint label="Audit Ledger" value="Postgres-backed history" />
            </div>
          </div>

          <section className="self-end border border-neutral-800 bg-neutral-900 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">Demo Controls</p>
                <p className="mt-1 truncate text-xs text-neutral-400">{apiHost}</p>
              </div>
              <button
                onClick={createDemo}
                disabled={loading}
                className="h-10 shrink-0 rounded-md bg-white px-4 text-sm font-semibold text-neutral-950 transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:bg-neutral-600 disabled:text-neutral-300"
              >
                {loading ? "Analyzing..." : "Create Session"}
              </button>
            </div>

            <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto]">
              <input
                value={slackChannel}
                onChange={(event) => setSlackChannel(event.target.value)}
                className="h-10 rounded-md border border-neutral-700 bg-neutral-950 px-3 text-sm text-white outline-none focus:border-white"
                aria-label="Slack channel ID"
              />
              <button
                onClick={sendSlackCards}
                disabled={slackLoading}
                className="h-10 rounded-md border border-neutral-700 px-4 text-sm font-semibold text-white hover:border-white disabled:cursor-not-allowed disabled:text-neutral-500"
              >
                {slackLoading ? "Sending..." : "Send Slack Cards"}
              </button>
            </div>
            {slackResult ? (
              <div className="mt-3 border border-sky-800 bg-sky-950/40 px-3 py-2 text-xs text-sky-100">
                Posted {slackResult.posted.length} card
                {slackResult.posted.length === 1 ? "" : "s"} for{" "}
                {slackResult.session_id.slice(0, 12)}.
              </div>
            ) : null}
          </section>
        </header>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Metric label="Session" value={demo ? demo.session.id.slice(0, 13) : "Not started"} />
          <Metric label="Trace Events" value={String(traces.length)} />
          <Metric label="Pending Gates" value={String(pendingCount)} accent="sky" />
          <Metric label="Resolved Actions" value={String(resolvedCount)} accent="green" />
          <Metric
            label="Critical Blocks"
            value={String(criticalCount)}
            accent={criticalCount > 0 ? "red" : "neutral"}
          />
        </section>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
          <div className="flex flex-col gap-5">
            <section>
              <div className="flex flex-col gap-3 border-b border-neutral-300 pb-4 md:flex-row md:items-end md:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase text-neutral-500">Live Review</p>
                  <h2 className="mt-1 text-2xl font-semibold">Decision Queue</h2>
                  <p className="mt-1 max-w-2xl text-sm text-neutral-600">
                    {demo
                      ? demo.session.original_instruction
                      : "Safe reads, gated writes, and destructive migration attempts are staged for review."}
                  </p>
                </div>
                <input
                  value={decisionNote}
                  onChange={(event) => setDecisionNote(event.target.value)}
                  className="h-10 w-full rounded-md border border-neutral-300 bg-white px-3 text-sm outline-none focus:border-neutral-950 md:w-[430px]"
                  aria-label="Decision note"
                />
              </div>

              <div className="mt-4 flex flex-col gap-4">
                {gates.length === 0 ? (
                  <EmptyState onCreate={createDemo} loading={loading} />
                ) : (
                  gates.map((gate) => (
                    <DecisionCard
                      key={gate.id}
                      gate={gate}
                      trace={traceByProposal.get(gate.proposal_id)}
                      onDecision={decide}
                    />
                  ))
                )}
              </div>
            </section>
          </div>

          <aside className="flex flex-col gap-5">
            <SystemPanel health={health} />
            <AnalyticsPanel analytics={analytics} />
            <TimelinePanel traces={traces} />
          </aside>
        </section>
      </section>
    </main>
  );
}

async function fetchAnalytics(sessionId: string) {
  const response = await fetch(`${API_URL}/sessions/${sessionId}/analytics`);
  if (!response.ok) throw new Error(`Analytics failed with ${response.status}`);
  return (await response.json()) as LedgerAnalytics;
}

function healthLabel(health: HealthState) {
  if (health === "online") return "Backend Online";
  if (health === "offline") return "Backend Offline";
  return "Checking Backend";
}

function titleCase(value: string) {
  return value
    .replace(/[_.]/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function toolLabel(value: string | undefined) {
  const labels: Record<string, string> = {
    "fs.read": "File Read",
    "fs.write": "File Write",
    "fs.delete": "File Delete",
    "shell.run": "Shell Command",
    "db.query": "Database Query",
    "api.call": "API Call",
  };
  return value ? (labels[value] ?? titleCase(value)) : "Tool Call";
}

function Pill({
  label,
  tone,
}: {
  label: string;
  tone: "green" | "blue" | "amber" | "neutral" | "dark";
}) {
  const styles = {
    green: "border-emerald-400/50 bg-emerald-400/10 text-emerald-100",
    blue: "border-sky-400/50 bg-sky-400/10 text-sky-100",
    amber: "border-amber-400/50 bg-amber-400/10 text-amber-100",
    neutral: "border-neutral-200 bg-white text-neutral-700",
    dark: "border-neutral-700 bg-neutral-900 text-white",
  };
  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${styles[tone]}`}>
      {label}
    </span>
  );
}

function ProofPoint({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-neutral-800 bg-neutral-900 px-3 py-2">
      <p className="text-xs font-semibold uppercase text-neutral-500">{label}</p>
      <p className="mt-1 font-medium text-neutral-100">{value}</p>
    </div>
  );
}

function Metric({
  label,
  value,
  accent = "neutral",
}: {
  label: string;
  value: string;
  accent?: "neutral" | "green" | "sky" | "red";
}) {
  const accentStyles = {
    neutral: "border-neutral-200",
    green: "border-emerald-300",
    sky: "border-sky-300",
    red: "border-red-300",
  };
  return (
    <div className={`rounded-lg border bg-white p-4 shadow-sm ${accentStyles[accent]}`}>
      <p className="text-xs font-semibold uppercase text-neutral-500">{label}</p>
      <p className="mt-2 truncate text-2xl font-semibold">{value}</p>
    </div>
  );
}

function SystemPanel({ health }: { health: HealthState }) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase text-neutral-500">Infrastructure</p>
      <h2 className="mt-1 text-lg font-semibold">Runtime Status</h2>
      <div className="mt-4 flex flex-col gap-3">
        <StatusRow label="Backend API" value={healthLabel(health)} ok={health === "online"} />
        <StatusRow label="OpenAI Layer" value="Structured Outputs Enabled" ok />
        <StatusRow label="Slack Surface" value="Hosted Interactivity Live" ok />
        <StatusRow label="Ledger Store" value="Render Postgres Attached" ok />
      </div>
    </section>
  );
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md bg-neutral-50 px-3 py-2">
      <div>
        <p className="text-sm font-medium text-neutral-900">{label}</p>
        <p className="text-xs text-neutral-500">{value}</p>
      </div>
      <span
        className={`h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`}
        aria-hidden="true"
      />
    </div>
  );
}

function AnalyticsPanel({ analytics }: { analytics: LedgerAnalytics | null }) {
  const trust = analytics ? Math.round(analytics.trust_score.score * 100) : 0;
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-neutral-500">Audit Intelligence</p>
          <h2 className="mt-1 text-lg font-semibold">Ledger Analytics</h2>
          <p className="mt-1 text-sm text-neutral-500">
            {analytics ? `${analytics.trust_score.total_actions} Actions Recorded` : "Awaiting Session"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-semibold">{analytics ? `${trust}%` : "--"}</p>
          <p className="text-xs uppercase text-neutral-500">Trust</p>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        <ProgressBar value={trust} />
        <BucketList title="Approval Patterns" buckets={analytics?.approval_patterns ?? []} />
        <BucketList title="Risk Distribution" buckets={analytics?.risk_distribution ?? []} />

        <div>
          <p className="text-sm font-semibold">Drift Flags</p>
          {analytics?.drift_history.length ? (
            <div className="mt-2 flex flex-col gap-2">
              {analytics.drift_history.map((item) => (
                <div
                  key={item.gate_id}
                  className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
                >
                  <p className="font-medium">
                    {item.risk_level} / {item.status.replace("_", " ")}
                  </p>
                  <p className="mt-1 leading-5">{item.drift_flag}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 rounded-md bg-neutral-50 px-3 py-2 text-sm text-neutral-500">
              No drift records yet.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 rounded-full bg-neutral-100">
      <div
        className="h-2 rounded-full bg-emerald-600 transition-all"
        style={{ width: `${Math.max(0, Math.min(value, 100))}%` }}
      />
    </div>
  );
}

function BucketList({ title, buckets }: { title: string; buckets: CountBucket[] }) {
  return (
    <div>
      <p className="text-sm font-semibold">{title}</p>
      <div className="mt-2 flex flex-col gap-2">
        {buckets.length === 0 ? (
          <p className="rounded-md bg-neutral-50 px-3 py-2 text-sm text-neutral-500">
            No records yet.
          </p>
        ) : (
          buckets.map((bucket) => (
            <div key={bucket.name} className="flex items-center justify-between text-sm">
              <span className="text-neutral-600">{titleCase(bucket.name)}</span>
              <span className="rounded bg-neutral-100 px-2 py-0.5 font-semibold">
                {bucket.count}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function TimelinePanel({ traces }: { traces: TraceEvent[] }) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase text-neutral-500">Trace Capture</p>
      <h2 className="mt-1 text-lg font-semibold">Execution Timeline</h2>
      <div className="mt-4 flex flex-col gap-3">
        {traces.length === 0 ? (
          <div className="rounded-md bg-neutral-50 px-3 py-3 text-sm text-neutral-500">
            Waiting for intercepted tool calls.
          </div>
        ) : (
          traces.map((trace, index) => (
            <div key={trace.id} className="rounded-md border border-neutral-100 bg-neutral-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase text-neutral-500">Step {index + 1}</p>
                <p className="text-xs text-neutral-500">{toolLabel(trace.tool_name)}</p>
              </div>
              <p className="mt-2 text-sm font-medium">{trace.stated_reason}</p>
              <code className="mt-2 block overflow-x-auto rounded bg-white p-2 text-xs text-neutral-700">
                {JSON.stringify(trace.params)}
              </code>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function EmptyState({ onCreate, loading }: { onCreate: () => void; loading: boolean }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <PreviewCard
        title="Safe Inspection"
        risk="low"
        body="Read-only calls pass automatically and still enter the ledger."
      />
      <PreviewCard
        title="Gated Write"
        risk="medium"
        body="Code changes get trajectory, confidence, drift, and approval controls."
      />
      <PreviewCard
        title="Destructive Action"
        risk="critical"
        body="Migration deletes are blocked and preserved as auditable decisions."
      />
      <div className="rounded-lg border border-dashed border-neutral-300 bg-neutral-50 p-5 lg:col-span-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-semibold">No active session</p>
            <p className="mt-1 text-sm text-neutral-500">
              The hosted console is connected and ready to generate the full review ledger.
            </p>
          </div>
          <button
            onClick={onCreate}
            disabled={loading}
            className="h-10 rounded-md bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-400"
          >
            {loading ? "Analyzing..." : "Run Full Demo"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PreviewCard({ title, risk, body }: { title: string; risk: RiskLevel; body: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4">
      <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${riskStyles[risk]}`}>
        {risk}
      </span>
      <p className="mt-4 font-semibold">{title}</p>
      <p className="mt-2 text-sm leading-6 text-neutral-600">{body}</p>
    </div>
  );
}

function DecisionCard({
  gate,
  trace,
  onDecision,
}: {
  gate: Gate;
  trace: TraceEvent | undefined;
  onDecision: (gate: Gate, action: "approve" | "block" | "modify") => Promise<void>;
}) {
  const card = gate.intelligence_card;
  const risk = card?.risk_badge ?? gate.risk_assessment.risk_level;
  const disabled = gate.status !== "pending";
  const confidence = Math.round((card?.confidence ?? 0) * 100);

  return (
    <article className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${riskStyles[risk]}`}
            >
              {risk}
            </span>
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusStyles[gate.status]}`}
            >
              {titleCase(gate.status)}
            </span>
            <span className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold uppercase text-neutral-600">
              {confidence}% confidence
            </span>
          </div>
          <h3 className="mt-3 text-xl font-semibold">
            {toolLabel(trace?.tool_name)} on{" "}
            {gate.risk_assessment.affected_files[0] ?? "external state"}
          </h3>
        </div>
        <p className="rounded-md bg-neutral-950 px-3 py-2 text-sm font-medium text-white">
          {titleCase(gate.policy_decision.action)}
        </p>
      </div>

      <p className="mt-4 text-base leading-7 text-neutral-800">
        {card?.summary ?? "No summary available."}
      </p>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Fact label="Reversibility" value={titleCase(gate.risk_assessment.reversibility)} />
        <Fact label="Blast Radius" value={titleCase(gate.risk_assessment.blast_radius)} />
        <Fact
          label="Policy Source"
          value={titleCase(gate.policy_decision.matched_policy ?? "semantic risk")}
        />
      </div>

      <section className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-md bg-neutral-50 p-3">
          <p className="text-xs font-semibold uppercase text-neutral-500">Trajectory</p>
          <p className="mt-2 text-sm leading-6 text-neutral-700">
            {card?.trajectory_preview ?? "No trajectory preview available."}
          </p>
        </div>
        <div className="rounded-md bg-neutral-50 p-3">
          <p className="text-xs font-semibold uppercase text-neutral-500">Evidence</p>
          <ul className="mt-2 flex flex-col gap-1 text-sm leading-6 text-neutral-700">
            {gate.risk_assessment.evidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </section>

      {card?.drift_flag ? (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
          {card.drift_flag}
        </p>
      ) : null}

      {gate.human_reason ? (
        <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
          {gate.human_reason}
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          onClick={() => onDecision(gate, "approve")}
          disabled={disabled}
          className="h-10 rounded-md bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral-500"
        >
          Approve
        </button>
        <button
          onClick={() => onDecision(gate, "block")}
          disabled={disabled}
          className="h-10 rounded-md border border-red-700 px-4 text-sm font-semibold text-red-800 hover:bg-red-50 disabled:cursor-not-allowed disabled:border-neutral-200 disabled:text-neutral-400"
        >
          Block
        </button>
        <button
          onClick={() => onDecision(gate, "modify")}
          disabled={disabled}
          className="h-10 rounded-md border border-neutral-300 px-4 text-sm font-semibold text-neutral-800 hover:border-neutral-950 disabled:cursor-not-allowed disabled:border-neutral-200 disabled:text-neutral-400"
        >
          Modify
        </button>
      </div>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-neutral-100 bg-neutral-50 p-3">
      <p className="text-xs font-semibold uppercase text-neutral-500">{label}</p>
      <p className="mt-1 truncate font-medium text-neutral-900">{value}</p>
    </div>
  );
}
