"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

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

const riskTone: Record<RiskLevel, string> = {
  low: "bg-emerald-500",
  medium: "bg-amber-500",
  high: "bg-orange-600",
  critical: "bg-red-600",
};

const statusTone: Record<GateStatus, string> = {
  pending: "border-sky-300 bg-sky-50 text-sky-800",
  approved: "border-emerald-300 bg-emerald-50 text-emerald-800",
  blocked: "border-red-300 bg-red-50 text-red-800",
  modified: "border-violet-300 bg-violet-50 text-violet-800",
  auto_executed: "border-neutral-300 bg-neutral-100 text-neutral-700",
};

export default function Home() {
  const [demo, setDemo] = useState<DemoResponse | null>(null);
  const [analytics, setAnalytics] = useState<LedgerAnalytics | null>(null);
  const [selectedGateId, setSelectedGateId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [slackLoading, setSlackLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthState>("checking");
  const [slackChannel, setSlackChannel] = useState(DEFAULT_SLACK_CHANNEL);
  const [decisionNote, setDecisionNote] = useState("Reviewed in AgentLens hosted console.");
  const [slackResult, setSlackResult] = useState<SlackSendResult | null>(null);

  useEffect(() => {
    let mounted = true;
    fetch(`${API_URL}/health`)
      .then((response) => {
        if (mounted) setHealth(response.ok ? "online" : "offline");
      })
      .catch(() => {
        if (mounted) setHealth("offline");
      });
    return () => {
      mounted = false;
    };
  }, []);

  const gates = demo?.timeline.gates ?? [];
  const traces = demo?.timeline.traces ?? [];
  const selectedGate = gates.find((gate) => gate.id === selectedGateId) ?? gates[0] ?? null;
  const traceByProposal = useMemo(
    () => new Map(traces.map((trace) => [trace.proposal_id, trace])),
    [traces],
  );
  const pendingCount = gates.filter((gate) => gate.status === "pending").length;
  const criticalCount = gates.filter((gate) => gate.risk_assessment.risk_level === "critical").length;
  const resolvedCount = gates.filter((gate) => gate.status !== "pending").length;
  const trustScore = analytics ? Math.round(analytics.trust_score.score * 100) : null;
  const apiHost = API_URL.replace(/^https?:\/\//, "");

  async function createDemo() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/demo/session`, { method: "POST" });
      if (!response.ok) throw new Error(`Demo failed with ${response.status}`);
      const nextDemo = (await response.json()) as DemoResponse;
      setDemo(nextDemo);
      setSelectedGateId(nextDemo.timeline.gates.find((gate) => gate.status === "pending")?.id ?? nextDemo.timeline.gates[0]?.id ?? null);
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
              "Continue only after inspecting references and proposing a safer scoped change.",
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
        const replace = (item: Gate) => (item.id === updated.id ? updated : item);
        return {
          ...current,
          gates: current.gates.map(replace),
          timeline: { ...current.timeline, gates: current.timeline.gates.map(replace) },
        };
      });
      setAnalytics(await fetchAnalytics(updated.session_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit decision");
    }
  }

  return (
    <main className="min-h-screen bg-[#f4f4f1] text-neutral-950">
      <div className="grid min-h-screen lg:grid-cols-[264px_minmax(0,1fr)]">
        <aside className="hidden border-r border-neutral-800 bg-neutral-950 text-white lg:flex lg:flex-col">
          <div className="border-b border-neutral-800 px-6 py-5">
            <p className="text-lg font-semibold">AgentLens</p>
            <p className="mt-1 text-xs uppercase text-neutral-500">Agent Risk Control</p>
          </div>
          <nav className="flex flex-1 flex-col gap-1 px-3 py-4 text-sm">
            <NavItem label="Review Queue" active />
            <NavItem label="Trajectory" />
            <NavItem label="Policy Ledger" />
            <NavItem label="Slack Surface" />
            <NavItem label="Audit Events" />
          </nav>
          <div className="border-t border-neutral-800 p-4">
            <StatusLine label="Backend" value={healthLabel(health)} ok={health === "online"} />
            <StatusLine label="Database" value="Postgres Connected" ok />
            <StatusLine label="OpenAI" value="Structured Outputs" ok />
          </div>
        </aside>

        <section className="min-w-0">
          <header className="border-b border-neutral-200 bg-white">
            <div className="flex flex-col gap-4 px-5 py-4 xl:flex-row xl:items-center xl:justify-between xl:px-7">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge label="Hosted Demo" tone="blue" />
                  <Badge label={healthLabel(health)} tone={health === "online" ? "green" : "amber"} />
                  <span className="truncate text-xs text-neutral-500">{apiHost}</span>
                </div>
                <h1 className="mt-2 text-2xl font-semibold tracking-normal text-neutral-950">
                  Agent Oversight Workspace
                </h1>
                <p className="mt-1 max-w-3xl text-sm text-neutral-600">
                  Intercept agent tool calls, classify risk, request approval, and preserve a durable audit trail.
                </p>
              </div>

              <div className="grid gap-2 sm:grid-cols-[auto_170px_auto]">
                <button
                  onClick={createDemo}
                  disabled={loading}
                  className="h-10 rounded-md bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-400"
                >
                  {loading ? "Running Analysis" : "Run Demo Session"}
                </button>
                <input
                  value={slackChannel}
                  onChange={(event) => setSlackChannel(event.target.value)}
                  className="h-10 rounded-md border border-neutral-300 bg-white px-3 text-sm font-medium outline-none focus:border-neutral-950"
                  aria-label="Slack channel ID"
                />
                <button
                  onClick={sendSlackCards}
                  disabled={slackLoading}
                  className="h-10 rounded-md border border-neutral-300 bg-white px-4 text-sm font-semibold text-neutral-900 hover:border-neutral-950 disabled:cursor-not-allowed disabled:text-neutral-400"
                >
                  {slackLoading ? "Sending" : "Send To Slack"}
                </button>
              </div>
            </div>
          </header>

          <div className="flex flex-col gap-5 px-5 py-5 xl:px-7">
            {error ? (
              <div className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
            ) : null}
            {slackResult ? (
              <div className="border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
                Posted {slackResult.posted.length} Slack approval card
                {slackResult.posted.length === 1 ? "" : "s"} for session{" "}
                {slackResult.session_id.slice(0, 12)}.
              </div>
            ) : null}

            <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <Metric label="Session" value={demo ? demo.session.id.slice(0, 13) : "Not Started"} />
              <Metric label="Trace Events" value={String(traces.length)} />
              <Metric label="Pending Gates" value={String(pendingCount)} accent="sky" />
              <Metric label="Resolved" value={String(resolvedCount)} accent="green" />
              <Metric label="Critical" value={String(criticalCount)} accent={criticalCount ? "red" : "neutral"} />
            </section>

            <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
              <div className="flex min-w-0 flex-col gap-5">
                <PanelHeader
                  eyebrow="Live Review"
                  title="Decision Queue"
                  body={
                    demo
                      ? demo.session.original_instruction
                      : "A complete demo run will stage a safe read, a gated code write, and a blocked migration delete."
                  }
                />
                {gates.length === 0 ? (
                  <EmptyQueue onCreate={createDemo} loading={loading} />
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-neutral-200 bg-white shadow-sm">
                    <div className="grid min-w-[640px] grid-cols-[90px_minmax(0,1fr)_118px_88px] border-b border-neutral-200 bg-neutral-50 px-4 py-2 text-xs font-semibold uppercase text-neutral-500">
                      <span>Risk</span>
                      <span>Action</span>
                      <span>Status</span>
                      <span>Confidence</span>
                    </div>
                    {gates.map((gate) => (
                      <QueueRow
                        key={gate.id}
                        gate={gate}
                        trace={traceByProposal.get(gate.proposal_id)}
                        selected={selectedGate?.id === gate.id}
                        onSelect={() => setSelectedGateId(gate.id)}
                      />
                    ))}
                  </div>
                )}

                <div className="grid gap-5 xl:grid-cols-2">
                  <TimelinePanel traces={traces} />
                  <AnalyticsPanel analytics={analytics} trustScore={trustScore} />
                </div>
              </div>

              <Inspector
                gate={selectedGate}
                trace={selectedGate ? traceByProposal.get(selectedGate.proposal_id) : undefined}
                decisionNote={decisionNote}
                onDecisionNote={setDecisionNote}
                onDecision={decide}
              />
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}

async function fetchAnalytics(sessionId: string) {
  const response = await fetch(`${API_URL}/sessions/${sessionId}/analytics`);
  if (!response.ok) throw new Error(`Analytics failed with ${response.status}`);
  return (await response.json()) as LedgerAnalytics;
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

function healthLabel(health: HealthState) {
  if (health === "online") return "Backend Online";
  if (health === "offline") return "Backend Offline";
  return "Checking Backend";
}

function NavItem({ label, active = false }: { label: string; active?: boolean }) {
  return (
    <div
      className={`rounded-md px-3 py-2 ${
        active ? "bg-white text-neutral-950" : "text-neutral-400 hover:bg-neutral-900 hover:text-white"
      }`}
    >
      {label}
    </div>
  );
}

function StatusLine({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div>
        <p className="text-xs uppercase text-neutral-500">{label}</p>
        <p className="text-sm text-neutral-200">{value}</p>
      </div>
      <span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-400" : "bg-amber-400"}`} />
    </div>
  );
}

function Badge({ label, tone }: { label: string; tone: "blue" | "green" | "amber" | "neutral" }) {
  const styles = {
    blue: "border-sky-200 bg-sky-50 text-sky-800",
    green: "border-emerald-200 bg-emerald-50 text-emerald-800",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    neutral: "border-neutral-200 bg-neutral-50 text-neutral-700",
  };
  return (
    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${styles[tone]}`}>
      {label}
    </span>
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
  const styles = {
    neutral: "border-neutral-200",
    green: "border-emerald-300",
    sky: "border-sky-300",
    red: "border-red-300",
  };
  return (
    <div className={`rounded-lg border bg-white p-4 shadow-sm ${styles[accent]}`}>
      <p className="text-xs font-semibold uppercase text-neutral-500">{label}</p>
      <p className="mt-2 truncate text-2xl font-semibold">{value}</p>
    </div>
  );
}

function PanelHeader({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="border-b border-neutral-300 pb-3">
      <p className="text-xs font-semibold uppercase text-neutral-500">{eyebrow}</p>
      <div className="mt-1 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <h2 className="text-2xl font-semibold">{title}</h2>
        <p className="max-w-2xl text-sm leading-6 text-neutral-600">{body}</p>
      </div>
    </div>
  );
}

function EmptyQueue({ onCreate, loading }: { onCreate: () => void; loading: boolean }) {
  const rows = [
    ["Low", "File Read", "Auto Execute", "Read-only inspection enters the ledger."],
    ["Medium", "File Write", "Require Approval", "Scoped code edits receive trajectory and drift analysis."],
    ["Critical", "File Delete", "Block And Alert", "Migration deletes are stopped before execution."],
  ];
  return (
    <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
      {rows.map(([risk, action, policy, note]) => (
        <div key={action} className="grid gap-3 border-b border-neutral-100 px-4 py-4 last:border-b-0 md:grid-cols-[110px_150px_160px_1fr]">
          <span className="text-sm font-semibold">{risk}</span>
          <span className="text-sm text-neutral-700">{action}</span>
          <span className="text-sm text-neutral-700">{policy}</span>
          <span className="text-sm text-neutral-500">{note}</span>
        </div>
      ))}
      <div className="flex flex-col gap-3 border-t border-neutral-200 bg-neutral-50 px-4 py-4 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-neutral-600">Run the demo to populate the live queue and inspector.</p>
        <button
          onClick={onCreate}
          disabled={loading}
          className="h-10 rounded-md bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-400"
        >
          {loading ? "Running Analysis" : "Run Demo Session"}
        </button>
      </div>
    </div>
  );
}

function QueueRow({
  gate,
  trace,
  selected,
  onSelect,
}: {
  gate: Gate;
  trace: TraceEvent | undefined;
  selected: boolean;
  onSelect: () => void;
}) {
  const card = gate.intelligence_card;
  const risk = gate.risk_assessment.risk_level;
  const confidence = Math.round((card?.confidence ?? 0) * 100);
  return (
    <button
      onClick={onSelect}
      className={`grid min-w-[640px] w-full grid-cols-[90px_minmax(0,1fr)_118px_88px] items-center gap-3 border-b border-neutral-100 px-4 py-4 text-left last:border-b-0 hover:bg-neutral-50 ${
        selected ? "bg-neutral-50" : "bg-white"
      }`}
    >
      <span className="flex items-center gap-2 text-sm font-semibold">
        <span className={`h-2.5 w-2.5 rounded-full ${riskTone[risk]}`} />
        {titleCase(risk)}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold">
          {toolLabel(trace?.tool_name)} on {gate.risk_assessment.affected_files[0] ?? "External State"}
        </span>
        <span className="mt-1 block truncate text-xs text-neutral-500">
          {card?.summary ?? trace?.stated_reason ?? "No summary available"}
        </span>
      </span>
      <span
        className={`w-fit rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone[gate.status]}`}
      >
        {titleCase(gate.status)}
      </span>
      <span className="text-sm font-semibold">{confidence}%</span>
    </button>
  );
}

function Inspector({
  gate,
  trace,
  decisionNote,
  onDecisionNote,
  onDecision,
}: {
  gate: Gate | null;
  trace: TraceEvent | undefined;
  decisionNote: string;
  onDecisionNote: (value: string) => void;
  onDecision: (gate: Gate, action: "approve" | "block" | "modify") => Promise<void>;
}) {
  if (!gate) {
    return (
      <aside className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase text-neutral-500">Inspector</p>
        <h2 className="mt-2 text-xl font-semibold">No Action Selected</h2>
        <p className="mt-3 text-sm leading-6 text-neutral-600">
          Run a demo session to inspect risk, trajectory, drift, policy, and approval controls.
        </p>
      </aside>
    );
  }

  const card = gate.intelligence_card;
  const disabled = gate.status !== "pending";
  return (
    <aside className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase text-neutral-500">Inspector</p>
      <div className="mt-3 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">{toolLabel(trace?.tool_name)}</h2>
          <p className="mt-1 text-sm text-neutral-500">
            {gate.risk_assessment.affected_files[0] ?? "External State"}
          </p>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone[gate.status]}`}>
          {titleCase(gate.status)}
        </span>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3">
        <Fact label="Risk" value={titleCase(gate.risk_assessment.risk_level)} />
        <Fact label="Blast" value={titleCase(gate.risk_assessment.blast_radius)} />
        <Fact label="Confidence" value={`${Math.round((card?.confidence ?? 0) * 100)}%`} />
      </div>

      <Section title="Recommendation">
        <p>{card?.summary ?? "No intelligence summary available."}</p>
      </Section>

      <Section title="Trajectory">
        <p>{card?.trajectory_preview ?? "No trajectory preview available."}</p>
      </Section>

      <Section title="Evidence">
        <ul className="flex flex-col gap-2">
          {gate.risk_assessment.evidence.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Section>

      {card?.drift_flag ? (
        <Section title="Drift">
          <p>{card.drift_flag}</p>
        </Section>
      ) : null}

      {gate.human_reason ? (
        <Section title="Decision">
          <p>{gate.human_reason}</p>
        </Section>
      ) : null}

      <label className="mt-5 block text-xs font-semibold uppercase text-neutral-500" htmlFor="decision-note">
        Decision Note
      </label>
      <input
        id="decision-note"
        value={decisionNote}
        onChange={(event) => onDecisionNote(event.target.value)}
        className="mt-2 h-10 w-full rounded-md border border-neutral-300 px-3 text-sm outline-none focus:border-neutral-950"
      />

      <div className="mt-4 grid grid-cols-3 gap-2">
        <button
          onClick={() => onDecision(gate, "approve")}
          disabled={disabled}
          className="h-10 rounded-md bg-neutral-950 text-sm font-semibold text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral-500"
        >
          Approve
        </button>
        <button
          onClick={() => onDecision(gate, "block")}
          disabled={disabled}
          className="h-10 rounded-md border border-red-700 text-sm font-semibold text-red-800 hover:bg-red-50 disabled:cursor-not-allowed disabled:border-neutral-200 disabled:text-neutral-400"
        >
          Block
        </button>
        <button
          onClick={() => onDecision(gate, "modify")}
          disabled={disabled}
          className="h-10 rounded-md border border-neutral-300 text-sm font-semibold text-neutral-800 hover:border-neutral-950 disabled:cursor-not-allowed disabled:border-neutral-200 disabled:text-neutral-400"
        >
          Modify
        </button>
      </div>
    </aside>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-neutral-200 bg-neutral-50 p-3">
      <p className="text-xs font-semibold uppercase text-neutral-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-neutral-950">{value}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-5 border-t border-neutral-200 pt-4">
      <p className="text-xs font-semibold uppercase text-neutral-500">{title}</p>
      <div className="mt-2 text-sm leading-6 text-neutral-700">{children}</div>
    </section>
  );
}

function TimelinePanel({ traces }: { traces: TraceEvent[] }) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase text-neutral-500">Trace Capture</p>
      <h2 className="mt-1 text-lg font-semibold">Execution Timeline</h2>
      <div className="mt-4 flex flex-col gap-3">
        {traces.length === 0 ? (
          <p className="text-sm text-neutral-500">No intercepted tool calls yet.</p>
        ) : (
          traces.map((trace, index) => (
            <div key={trace.id} className="border-l-2 border-neutral-300 pl-3">
              <p className="text-xs font-semibold uppercase text-neutral-500">
                Step {index + 1} / {toolLabel(trace.tool_name)}
              </p>
              <p className="mt-1 text-sm text-neutral-700">{trace.stated_reason}</p>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function AnalyticsPanel({
  analytics,
  trustScore,
}: {
  analytics: LedgerAnalytics | null;
  trustScore: number | null;
}) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-neutral-500">Audit Intelligence</p>
          <h2 className="mt-1 text-lg font-semibold">Ledger Analytics</h2>
        </div>
        <p className="text-2xl font-semibold">{trustScore === null ? "--" : `${trustScore}%`}</p>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-1">
        <BucketList title="Approval Patterns" buckets={analytics?.approval_patterns ?? []} />
        <BucketList title="Risk Distribution" buckets={analytics?.risk_distribution ?? []} />
      </div>
    </section>
  );
}

function BucketList({ title, buckets }: { title: string; buckets: CountBucket[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-neutral-500">{title}</p>
      <div className="mt-2 flex flex-col gap-2">
        {buckets.length === 0 ? (
          <p className="text-sm text-neutral-500">No records yet.</p>
        ) : (
          buckets.map((bucket) => (
            <div key={bucket.name} className="flex items-center justify-between text-sm">
              <span className="text-neutral-700">{titleCase(bucket.name)}</span>
              <span className="font-semibold">{bucket.count}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
