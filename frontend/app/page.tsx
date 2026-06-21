"use client";

import { useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_AGENTLENS_API_URL ?? "http://127.0.0.1:8000";

type RiskLevel = "low" | "medium" | "high" | "critical";
type GateStatus = "pending" | "approved" | "blocked" | "modified" | "auto_executed";

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

const riskStyles: Record<RiskLevel, string> = {
  low: "border-emerald-200 bg-emerald-50 text-emerald-800",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  high: "border-red-200 bg-red-50 text-red-800",
  critical: "border-red-300 bg-red-100 text-red-950",
};

export default function Home() {
  const [demo, setDemo] = useState<DemoResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionNote, setDecisionNote] = useState("Reviewed from local approval UI.");
  const [analytics, setAnalytics] = useState<LedgerAnalytics | null>(null);

  const gates = demo?.timeline.gates ?? [];
  const pendingCount = useMemo(
    () => gates.filter((gate) => gate.status === "pending").length,
    [gates],
  );
  const interventionRate = useMemo(() => {
    if (gates.length === 0) return 0;
    const gated = gates.filter((gate) => gate.status !== "auto_executed").length;
    return Math.round((gated / gates.length) * 100);
  }, [gates]);

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
    <main className="min-h-screen bg-neutral-50 text-neutral-950">
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-5 py-8">
        <header className="flex flex-col gap-5 border-b border-neutral-200 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-emerald-700">
              AgentLens Local Review
            </p>
            <h1 className="mt-2 max-w-3xl text-4xl font-semibold leading-tight">
              Approve agent direction with risk, drift, confidence, and trajectory in view.
            </h1>
          </div>
          <button
            onClick={createDemo}
            disabled={loading}
            className="h-11 rounded-md bg-neutral-950 px-5 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-400"
          >
            {loading ? "Creating..." : "Create Demo Session"}
          </button>
        </header>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}

        <section className="grid gap-4 md:grid-cols-4">
          <Metric label="Session" value={demo ? demo.session.id.slice(0, 12) : "Not started"} />
          <Metric label="Trace Events" value={String(demo?.timeline.traces.length ?? 0)} />
          <Metric label="Pending Gates" value={String(pendingCount)} />
          <Metric
            label="Trust Score"
            value={
              analytics
                ? `${Math.round(analytics.trust_score.score * 100)}%`
                : `${100 - interventionRate}%`
            }
          />
        </section>

        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <section className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Decision Cards</h2>
              <input
                value={decisionNote}
                onChange={(event) => setDecisionNote(event.target.value)}
                className="hidden h-10 w-80 rounded-md border border-neutral-300 bg-white px-3 text-sm outline-none focus:border-neutral-950 md:block"
                aria-label="Decision note"
              />
            </div>

            {gates.length === 0 ? (
              <EmptyState />
            ) : (
              gates.map((gate) => (
                <DecisionCard key={gate.id} gate={gate} onDecision={decide} />
              ))
            )}
          </section>

          <aside className="flex flex-col gap-4">
            <h2 className="text-xl font-semibold">Ledger Analytics</h2>
            <AnalyticsPanel analytics={analytics} />

            <h2 className="pt-2 text-xl font-semibold">Timeline</h2>
            <div className="rounded-lg border border-neutral-200 bg-white">
              {(demo?.timeline.traces ?? []).map((trace, index) => (
                <div key={trace.id} className="border-b border-neutral-100 p-4 last:border-b-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                    Step {index + 1}
                  </p>
                  <p className="mt-1 font-medium">{trace.tool_name}</p>
                  <p className="mt-1 text-sm text-neutral-600">{trace.stated_reason}</p>
                  <code className="mt-3 block overflow-x-auto rounded bg-neutral-100 p-2 text-xs text-neutral-700">
                    {JSON.stringify(trace.params)}
                  </code>
                </div>
              ))}
              {!demo ? <p className="p-4 text-sm text-neutral-500">No session yet.</p> : null}
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

async function fetchAnalytics(sessionId: string) {
  const response = await fetch(`${API_URL}/sessions/${sessionId}/analytics`);
  if (!response.ok) throw new Error(`Analytics failed with ${response.status}`);
  return (await response.json()) as LedgerAnalytics;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <p className="text-sm text-neutral-500">{label}</p>
      <p className="mt-2 truncate text-2xl font-semibold">{value}</p>
    </div>
  );
}

function AnalyticsPanel({ analytics }: { analytics: LedgerAnalytics | null }) {
  if (!analytics) {
    return (
      <div className="rounded-lg border border-neutral-200 bg-white p-4 text-sm text-neutral-500">
        Create a demo session to calculate trust, approval patterns, risk distribution, and drift.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-neutral-200 bg-white p-4">
        <p className="text-sm text-neutral-500">Actions without intervention</p>
        <p className="mt-2 text-3xl font-semibold">
          {Math.round(analytics.trust_score.score * 100)}%
        </p>
        <p className="mt-1 text-sm text-neutral-500">
          {analytics.trust_score.auto_executed} auto /{" "}
          {analytics.trust_score.total_actions} total
        </p>
      </div>

      <BucketList title="Approval Patterns" buckets={analytics.approval_patterns} />
      <BucketList title="Risk Distribution" buckets={analytics.risk_distribution} />

      <div className="rounded-lg border border-neutral-200 bg-white p-4">
        <p className="text-sm font-semibold">Drift History</p>
        {analytics.drift_history.length === 0 ? (
          <p className="mt-2 text-sm text-neutral-500">No drift flags in this session.</p>
        ) : (
          <div className="mt-3 flex flex-col gap-3">
            {analytics.drift_history.map((item) => (
              <div key={item.gate_id} className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
                <p className="font-medium">
                  {item.risk_level} / {item.status.replace("_", " ")}
                </p>
                <p className="mt-1">{item.drift_flag}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BucketList({ title, buckets }: { title: string; buckets: CountBucket[] }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <p className="text-sm font-semibold">{title}</p>
      <div className="mt-3 flex flex-col gap-2">
        {buckets.map((bucket) => (
          <div key={bucket.name} className="flex items-center justify-between text-sm">
            <span className="capitalize text-neutral-600">{bucket.name.replace("_", " ")}</span>
            <span className="font-semibold">{bucket.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-neutral-300 bg-white p-8 text-center">
      <p className="text-lg font-medium">No decision cards yet</p>
      <p className="mt-2 text-sm text-neutral-500">
        Create a demo session to replay safe reads, gated writes, and critical delete attempts.
      </p>
    </div>
  );
}

function DecisionCard({
  gate,
  onDecision,
}: {
  gate: Gate;
  onDecision: (gate: Gate, action: "approve" | "block" | "modify") => Promise<void>;
}) {
  const card = gate.intelligence_card;
  const risk = card?.risk_badge ?? gate.risk_assessment.risk_level;
  const disabled = gate.status !== "pending";

  return (
    <article className="rounded-lg border border-neutral-200 bg-white p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase ${riskStyles[risk]}`}
          >
            {risk}
          </span>
          <span className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold uppercase text-neutral-600">
            {gate.status.replace("_", " ")}
          </span>
          <span className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold uppercase text-neutral-600">
            {Math.round((card?.confidence ?? 0) * 100)}% confidence
          </span>
        </div>
        <p className="text-sm text-neutral-500">{gate.policy_decision.action}</p>
      </div>

      <p className="mt-4 text-lg leading-7">{card?.summary ?? "No summary available."}</p>
      <p className="mt-4 rounded-md bg-neutral-100 p-3 text-sm text-neutral-700">
        {card?.trajectory_preview ?? "No trajectory preview available."}
      </p>
      {card?.drift_flag ? (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {card.drift_flag}
        </p>
      ) : null}

      <div className="mt-4 grid gap-3 text-sm text-neutral-600 md:grid-cols-3">
        <Fact label="Reversibility" value={gate.risk_assessment.reversibility} />
        <Fact label="Blast radius" value={gate.risk_assessment.blast_radius} />
        <Fact label="Policy" value={gate.policy_decision.matched_policy ?? "semantic risk"} />
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          onClick={() => onDecision(gate, "approve")}
          disabled={disabled}
          className="h-10 rounded-md bg-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
        >
          Approve
        </button>
        <button
          onClick={() => onDecision(gate, "block")}
          disabled={disabled}
          className="h-10 rounded-md bg-red-700 px-4 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:bg-neutral-300"
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
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">{label}</p>
      <p className="mt-1 truncate font-medium text-neutral-800">{value}</p>
    </div>
  );
}
