"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

const API_URL = process.env.NEXT_PUBLIC_AGENTLENS_API_URL ?? "http://127.0.0.1:8000";
const DEFAULT_SLACK_CHANNEL = "C0BBW328TEF";
const ACTIVE_SESSION_STORAGE_KEY = "agentlens-active-session-id";

type RiskLevel = "low" | "medium" | "high" | "critical";
type GateStatus = "pending" | "approved" | "blocked" | "modified" | "auto_executed";
type HealthState = "checking" | "online" | "offline";
type View = "review" | "trajectory" | "policies" | "slack" | "audit";

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

type TimelineResponse = {
  session: DemoResponse["session"];
  traces: TraceEvent[];
  gates: Gate[];
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

const navItems: { id: View; label: string }[] = [
  { id: "review", label: "Review Queue" },
  { id: "trajectory", label: "Trajectory" },
  { id: "policies", label: "Policy Ledger" },
  { id: "slack", label: "Slack Surface" },
  { id: "audit", label: "Audit Events" },
];

const riskDot: Record<RiskLevel, string> = {
  low: "bg-emerald-500",
  medium: "bg-amber-500",
  high: "bg-orange-600",
  critical: "bg-red-600",
};

const riskChip: Record<RiskLevel, string> = {
  low: "border-emerald-200 bg-emerald-50 text-emerald-800",
  medium: "border-amber-200 bg-amber-50 text-amber-900",
  high: "border-orange-200 bg-orange-50 text-orange-900",
  critical: "border-red-200 bg-red-50 text-red-800",
};

const statusChip: Record<GateStatus, string> = {
  pending: "border-sky-200 bg-sky-50 text-sky-800",
  approved: "border-emerald-200 bg-emerald-50 text-emerald-800",
  blocked: "border-red-200 bg-red-50 text-red-800",
  modified: "border-violet-200 bg-violet-50 text-violet-800",
  auto_executed: "border-neutral-200 bg-neutral-100 text-neutral-700",
};

export default function Home() {
  const [activeView, setActiveView] = useState<View>("review");
  const [demo, setDemo] = useState<DemoResponse | null>(null);
  const [analytics, setAnalytics] = useState<LedgerAnalytics | null>(null);
  const [selectedGateId, setSelectedGateId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [slackLoading, setSlackLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthState>("checking");
  const [slackChannel, setSlackChannel] = useState(DEFAULT_SLACK_CHANNEL);
  const [codexPrompt, setCodexPrompt] = useState(
    "Inspect this repo and propose the next implementation step.",
  );
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

  useEffect(() => {
    const sessionId = window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
    if (sessionId) void refreshSession(sessionId);
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
  const localGuardMode = isLocalApi(API_URL);

  useEffect(() => {
    if (!demo?.session.id) return;
    const interval = window.setInterval(() => {
      void refreshSession(demo.session.id);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [demo?.session.id]);

  async function createDemo() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(localGuardMode ? `${API_URL}/codex/sessions` : `${API_URL}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          localGuardMode
            ? {
                prompt: codexPrompt,
                repo_path: ".",
                sandbox: "read-only",
              }
            : {
                original_instruction: codexPrompt,
                repo_path: ".",
              },
        ),
      });
      if (!response.ok) throw new Error(`Session failed with ${response.status}`);
      const body = await response.json();
      const session = (localGuardMode ? body.session : body) as DemoResponse["session"];
      window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, session.id);
      const nextGates = localGuardMode ? ((body.timeline?.gates ?? []) as Gate[]) : [];
      const nextTraces = localGuardMode ? ((body.timeline?.traces ?? []) as TraceEvent[]) : [];
      setDemo({ session, gates: nextGates, timeline: { traces: nextTraces, gates: nextGates } });
      setSelectedGateId(nextGates.find((gate) => gate.status === "pending")?.id ?? nextGates[0]?.id ?? null);
      setAnalytics(await fetchAnalytics(session.id));
      setActiveView("review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start supervision");
    } finally {
      setLoading(false);
    }
  }

  async function refreshSession(sessionId: string) {
    try {
      const response = await fetch(`${API_URL}/sessions/${sessionId}/timeline`);
      if (!response.ok) return;
      const timeline = (await response.json()) as TimelineResponse;
      setDemo((current) => {
        if (current && current.session.id !== sessionId) return current;
        return {
          session: timeline.session,
          gates: timeline.gates,
          timeline: { traces: timeline.traces, gates: timeline.gates },
        };
      });
      setSelectedGateId((current) => current ?? timeline.gates[0]?.id ?? null);
      setAnalytics(await fetchAnalytics(sessionId));
    } catch {
      return;
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
      setActiveView("slack");
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
    <main className="min-h-screen bg-[#f5f5f2] text-neutral-950">
      <div className="grid min-h-screen lg:grid-cols-[264px_minmax(0,1fr)]">
        <aside className="hidden border-r border-neutral-800 bg-neutral-950 text-white lg:flex lg:flex-col">
          <div className="border-b border-neutral-800 px-6 py-5">
            <p className="text-lg font-semibold leading-none">AgentLens</p>
            <p className="mt-3 text-xs uppercase tracking-wide text-neutral-500">Agent Risk Control</p>
          </div>
          <nav className="flex flex-1 flex-col gap-1 px-3 py-4 text-sm">
            {navItems.map((item) => (
              <NavItem
                key={item.id}
                label={item.label}
                active={activeView === item.id}
                onClick={() => setActiveView(item.id)}
              />
            ))}
          </nav>
          <div className="border-t border-neutral-800 p-4">
            <StatusLine label="Backend" value={healthLabel(health)} ok={health === "online"} />
            <StatusLine label="Database" value="Postgres Connected" ok />
            <StatusLine label="OpenAI" value="Structured Outputs" ok />
          </div>
        </aside>

        <section className="min-w-0">
          <header className="border-b border-neutral-200 bg-white">
            <div className="mx-auto flex max-w-[1680px] flex-col gap-4 px-5 py-4 xl:flex-row xl:items-center xl:justify-between xl:px-8">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge label="Live Review" tone="blue" />
                  <Badge label={healthLabel(health)} tone={health === "online" ? "green" : "amber"} />
                  <span className="truncate text-xs font-medium text-neutral-500">{apiHost}</span>
                </div>
                <h1 className="mt-2 text-[26px] font-semibold leading-tight tracking-normal">
                  Agent Oversight Workspace
                </h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-neutral-600">
                  Intercept agent tool calls, classify risk, request approval, and preserve a durable audit trail.
                </p>
              </div>

              <div className="grid gap-2 sm:grid-cols-[170px_120px]">
                <input
                  value={slackChannel}
                  onChange={(event) => setSlackChannel(event.target.value)}
                  className="h-10 rounded-md border border-neutral-300 bg-white px-3 text-sm font-medium outline-none focus:border-neutral-950"
                  aria-label="Slack channel ID"
                />
                <button
                  onClick={sendSlackCards}
                  disabled={slackLoading}
                  className="h-10 whitespace-nowrap rounded-md border border-neutral-300 bg-white px-4 text-sm font-semibold text-neutral-900 hover:border-neutral-950 disabled:cursor-not-allowed disabled:text-neutral-400"
                >
                  {slackLoading ? "Sending" : "Send To Slack"}
                </button>
              </div>
            </div>
          </header>

          <div className="mx-auto flex max-w-[1680px] flex-col gap-4 px-5 py-5 xl:px-8">
            {error ? <Notice tone="red">{error}</Notice> : null}
            {slackResult ? (
              <Notice tone="blue">
                Posted {slackResult.posted.length} Slack approval card
                {slackResult.posted.length === 1 ? "" : "s"} for session{" "}
                {slackResult.session_id.slice(0, 12)}.
              </Notice>
            ) : null}

            <TaskComposer
              value={codexPrompt}
              loading={loading}
              localGuardMode={localGuardMode}
              onChange={setCodexPrompt}
              onStart={createDemo}
            />

            <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <Metric label="Session" value={demo ? demo.session.id.slice(0, 13) : "Idle"} />
              <Metric label="Trace Events" value={String(traces.length)} />
              <Metric label="Pending Gates" value={String(pendingCount)} accent="sky" />
              <Metric label="Resolved" value={String(resolvedCount)} accent="green" />
              <Metric label="Critical" value={String(criticalCount)} accent={criticalCount ? "red" : "neutral"} />
            </section>

            {activeView === "review" ? (
              <ReviewView
                demo={demo}
                gates={gates}
                traces={traces}
                selectedGate={selectedGate}
                traceByProposal={traceByProposal}
                apiUrl={API_URL}
                codexPrompt={codexPrompt}
                localGuardMode={localGuardMode}
                decisionNote={decisionNote}
                onSelectGate={setSelectedGateId}
                onDecisionNote={setDecisionNote}
                onDecision={decide}
                analytics={analytics}
                trustScore={trustScore}
              />
            ) : null}
            {activeView === "trajectory" ? (
              <TrajectoryView gates={gates} traces={traces} traceByProposal={traceByProposal} onCreate={createDemo} />
            ) : null}
            {activeView === "policies" ? <PolicyLedgerView gates={gates} /> : null}
            {activeView === "slack" ? (
              <SlackSurfaceView
                channel={slackChannel}
                result={slackResult}
                loading={slackLoading}
                onChannel={setSlackChannel}
                onSend={sendSlackCards}
              />
            ) : null}
            {activeView === "audit" ? (
              <AuditEventsView gates={gates} traces={traces} analytics={analytics} trustScore={trustScore} />
            ) : null}
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

function ReviewView({
  demo,
  gates,
  traces,
  selectedGate,
  traceByProposal,
  apiUrl,
  codexPrompt,
  localGuardMode,
  decisionNote,
  onSelectGate,
  onDecisionNote,
  onDecision,
  analytics,
  trustScore,
}: {
  demo: DemoResponse | null;
  gates: Gate[];
  traces: TraceEvent[];
  selectedGate: Gate | null;
  traceByProposal: Map<string, TraceEvent>;
  apiUrl: string;
  codexPrompt: string;
  localGuardMode: boolean;
  decisionNote: string;
  onSelectGate: (id: string) => void;
  onDecisionNote: (value: string) => void;
  onDecision: (gate: Gate, action: "approve" | "block" | "modify") => Promise<void>;
  analytics: LedgerAnalytics | null;
  trustScore: number | null;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px] 2xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="flex min-w-0 flex-col gap-4">
        <PanelHeader
          eyebrow="Live Review"
          title="Decision Queue"
          body={
            demo
              ? demo.session.original_instruction
              : "AgentLens is connected and waiting for Codex to propose a tool call that needs judgment."
          }
        />
        {gates.length === 0 ? (
          <EmptyQueue
            sessionId={demo?.session.id ?? null}
            apiUrl={apiUrl}
            codexPrompt={codexPrompt}
            localGuardMode={localGuardMode}
          />
        ) : (
          <QueueTable
            gates={gates}
            selectedGate={selectedGate}
            traceByProposal={traceByProposal}
            onSelectGate={onSelectGate}
          />
        )}
        <div className="grid gap-4 xl:grid-cols-2">
          <TimelinePanel traces={traces} compact />
          <AnalyticsPanel analytics={analytics} trustScore={trustScore} compact />
        </div>
      </div>

      <Inspector
        gate={selectedGate}
        trace={selectedGate ? traceByProposal.get(selectedGate.proposal_id) : undefined}
        decisionNote={decisionNote}
        onDecisionNote={onDecisionNote}
        onDecision={onDecision}
      />
    </section>
  );
}

function TaskComposer({
  value,
  loading,
  localGuardMode,
  onChange,
  onStart,
}: {
  value: string;
  loading: boolean;
  localGuardMode: boolean;
  onChange: (value: string) => void;
  onStart: () => void;
}) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_180px] xl:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Codex Task</p>
            <Badge label={localGuardMode ? "Local Guard" : "Hosted Bridge"} tone="neutral" />
          </div>
          <label className="sr-only" htmlFor="codex-task">
            Codex task
          </label>
          <textarea
            id="codex-task"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            rows={3}
            className="mt-3 w-full resize-none rounded-md border border-neutral-300 bg-white px-3 py-3 text-sm leading-6 outline-none focus:border-neutral-950"
            placeholder="Ask Codex to inspect, implement, refactor, or verify something in this repo."
          />
          <p className="mt-2 text-xs leading-5 text-neutral-500">
            {localGuardMode
              ? "Runs Codex on this Mac through agentlens-guard, then gates risky tool calls locally."
              : "Creates a hosted review session and shows the local adapter command for forwarding Codex events."}
          </p>
        </div>
        <button
          onClick={onStart}
          disabled={loading || !value.trim()}
          className="h-11 whitespace-nowrap rounded-md bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-400"
        >
          {loading ? "Starting Session" : "Start Supervision"}
        </button>
      </div>
    </section>
  );
}

function TrajectoryView({
  gates,
  traces,
  traceByProposal,
  onCreate,
}: {
  gates: Gate[];
  traces: TraceEvent[];
  traceByProposal: Map<string, TraceEvent>;
  onCreate: () => void;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Panel>
        <PanelTitle eyebrow="Counterfactual Engine" title="Predicted Agent Direction" />
        {gates.length === 0 ? (
          <EmptyPanel
            title="No trajectory yet"
            body="Start supervision to capture Codex actions and generate predicted next steps with commitment points."
            action="Start Supervision"
            onAction={onCreate}
          />
        ) : (
          <div className="mt-5 grid gap-3">
            {gates.map((gate, index) => (
              <TrajectoryCard
                key={gate.id}
                gate={gate}
                trace={traceByProposal.get(gate.proposal_id)}
                step={index + 1}
              />
            ))}
          </div>
        )}
      </Panel>
      <Panel>
        <PanelTitle eyebrow="Trace Context" title="Captured Sequence" />
        <div className="mt-5">
          <TimelinePanel traces={traces} frameless compact />
        </div>
      </Panel>
    </section>
  );
}

function PolicyLedgerView({ gates }: { gates: Gate[] }) {
  const rows =
    gates.length > 0
      ? gates.map((gate) => ({
          name: gate.policy_decision.matched_policy ?? "Semantic Risk Recommendation",
          condition: gate.policy_decision.reason,
          action: titleCase(gate.policy_decision.action),
          risk: gate.risk_assessment.risk_level,
        }))
      : [
          {
            name: "Auto-Approve Safe Reads",
            condition: "Read-only file and inspection calls",
            action: "Auto Execute",
            risk: "low" as RiskLevel,
          },
          {
            name: "Review Gated Writes",
            condition: "Tracked source changes with medium reversibility",
            action: "Require Approval",
            risk: "medium" as RiskLevel,
          },
          {
            name: "Protect Migrations",
            condition: "Database migrations, deployment, and destructive operations",
            action: "Block And Alert",
            risk: "critical" as RiskLevel,
          },
        ];

  return (
    <Panel>
      <PanelTitle
        eyebrow="Policy Ledger"
        title="Standing Rules And Runtime Decisions"
        body="Policy evaluation is deterministic and recorded alongside semantic risk recommendations."
      />
      <div className="mt-5 overflow-x-auto border border-neutral-200 bg-white">
        <div className="grid min-w-[760px] grid-cols-[210px_minmax(0,1fr)_170px_120px] border-b border-neutral-200 bg-neutral-50 px-4 py-3 text-xs font-semibold uppercase text-neutral-500">
          <span>Rule</span>
          <span>Condition</span>
          <span>Decision</span>
          <span>Risk</span>
        </div>
        {rows.map((row, index) => (
          <div
            key={`${row.name}-${index}`}
            className="grid min-w-[760px] grid-cols-[210px_minmax(0,1fr)_170px_120px] items-center gap-3 border-b border-neutral-100 px-4 py-4 last:border-b-0"
          >
            <span className="text-sm font-semibold">{row.name}</span>
            <span className="truncate text-sm text-neutral-600">{row.condition}</span>
            <span className="text-sm font-medium">{row.action}</span>
            <RiskBadge risk={row.risk} />
          </div>
        ))}
      </div>
    </Panel>
  );
}

function SlackSurfaceView({
  channel,
  result,
  loading,
  onChannel,
  onSend,
}: {
  channel: string;
  result: SlackSendResult | null;
  loading: boolean;
  onChannel: (value: string) => void;
  onSend: () => void;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Panel>
        <PanelTitle
          eyebrow="Slack Surface"
          title="Ambient Approval Delivery"
          body="Cards are posted to Slack with signed button callbacks, then updated after a decision."
        />
        <div className="mt-5 grid gap-3 md:grid-cols-[220px_auto]">
          <input
            value={channel}
            onChange={(event) => onChannel(event.target.value)}
            className="h-10 rounded-md border border-neutral-300 bg-white px-3 text-sm font-medium outline-none focus:border-neutral-950"
            aria-label="Slack channel ID"
          />
          <button
            onClick={onSend}
            disabled={loading}
            className="h-10 w-fit rounded-md bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-400"
          >
            {loading ? "Sending Cards" : "Send Pending Cards"}
          </button>
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <SurfaceStep label="1" title="Gate Triggered" body="Risky action enters review." />
          <SurfaceStep label="2" title="Slack Posted" body="Human receives a concise card." />
          <SurfaceStep label="3" title="Ledger Updated" body="Decision is persisted and replayable." />
        </div>
      </Panel>
      <Panel>
        <PanelTitle eyebrow="Last Delivery" title={result ? "Cards Posted" : "No Cards Sent"} />
        {result ? (
          <div className="mt-5 grid gap-3">
            <Fact label="Session" value={result.session_id.slice(0, 14)} />
            <Fact label="Cards" value={String(result.posted.length)} />
            <Fact label="Channel" value={result.posted[0]?.channel ?? channel} />
          </div>
        ) : (
          <p className="mt-5 text-sm leading-6 text-neutral-600">
            Send cards after creating a session, or use this action to create a backend-owned approval session.
          </p>
        )}
      </Panel>
    </section>
  );
}

function AuditEventsView({
  gates,
  traces,
  analytics,
  trustScore,
}: {
  gates: Gate[];
  traces: TraceEvent[];
  analytics: LedgerAnalytics | null;
  trustScore: number | null;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Panel>
        <PanelTitle
          eyebrow="Audit Events"
          title="Session Ledger"
          body="Every trace, policy decision, and human action is recorded for replay."
        />
        <div className="mt-5 grid gap-3">
          {traces.length === 0 && gates.length === 0 ? (
            <p className="text-sm text-neutral-600">No audit events yet. Start supervision to populate the ledger.</p>
          ) : null}
          {traces.map((trace, index) => (
            <LedgerRow
              key={trace.id}
              label={`Trace ${index + 1}`}
              title={toolLabel(trace.tool_name)}
              body={trace.stated_reason ?? "No stated reason captured."}
            />
          ))}
          {gates.map((gate) => (
            <LedgerRow
              key={gate.id}
              label={titleCase(gate.status)}
              title={`${titleCase(gate.risk_assessment.risk_level)} risk gate`}
              body={gate.intelligence_card?.summary ?? gate.policy_decision.reason}
            />
          ))}
        </div>
      </Panel>
      <AnalyticsPanel analytics={analytics} trustScore={trustScore} />
    </section>
  );
}

function QueueTable({
  gates,
  selectedGate,
  traceByProposal,
  onSelectGate,
}: {
  gates: Gate[];
  selectedGate: Gate | null;
  traceByProposal: Map<string, TraceEvent>;
  onSelectGate: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-200 bg-white shadow-sm">
      <div className="grid min-w-[640px] grid-cols-[90px_minmax(0,1fr)_118px_88px] border-b border-neutral-200 bg-neutral-50 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-neutral-500">
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
          onSelect={() => onSelectGate(gate.id)}
        />
      ))}
    </div>
  );
}

function EmptyQueue({
  sessionId,
  apiUrl,
  codexPrompt,
  localGuardMode,
}: {
  sessionId: string | null;
  apiUrl: string;
  codexPrompt: string;
  localGuardMode: boolean;
}) {
  const command = sessionId
    ? `cd backend && uv run agentlens-demo --api-url ${apiUrl} --session-id ${sessionId} --repo /path/to/your/repo --codex-prompt ${JSON.stringify(codexPrompt)}`
    : null;
  const rows = [
    ["Low", "File Read", "Auto Execute", "Read-only inspection enters the ledger."],
    ["Medium", "File Write", "Require Approval", "Source changes receive trajectory and drift analysis."],
    ["Critical", "File Delete", "Block And Alert", "Migration deletes are stopped before execution."],
  ];
  return (
    <div className="rounded-lg border border-neutral-200 bg-white shadow-sm">
      {sessionId ? (
        <div className="grid gap-4 p-4">
          <div>
            <p className="text-sm font-semibold">Live session is listening</p>
            <p className="mt-1 text-sm leading-6 text-neutral-600">
              {localGuardMode
                ? "The local guard is connected. Start Supervision runs Codex on this machine and writes events into this local ledger."
                : "Run the adapter from your machine. It executes Codex locally, parses real Codex JSON events, and posts proposed tool calls into this hosted review queue."}
            </p>
          </div>
          {!localGuardMode ? (
            <code className="block overflow-x-auto rounded-md border border-neutral-200 bg-neutral-950 p-3 text-xs leading-6 text-neutral-100">
              {command}
            </code>
          ) : null}
          <div className="grid gap-0 divide-y divide-neutral-100 border border-neutral-200">
            {rows.map(([risk, action, policy, note]) => (
              <div
                key={action}
                className="grid gap-3 px-4 py-3 md:grid-cols-[110px_150px_160px_minmax(0,1fr)]"
              >
                <span className="text-sm font-semibold">{risk}</span>
                <span className="text-sm text-neutral-700">{action}</span>
                <span className="text-sm text-neutral-700">{policy}</span>
                <span className="text-sm text-neutral-500">{note}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="grid gap-0 divide-y divide-neutral-100">
          {rows.map(([risk, action, policy, note]) => (
            <div
              key={action}
              className="grid gap-3 px-4 py-4 md:grid-cols-[110px_150px_160px_minmax(0,1fr)]"
            >
              <span className="text-sm font-semibold">{risk}</span>
              <span className="text-sm text-neutral-700">{action}</span>
              <span className="text-sm text-neutral-700">{policy}</span>
              <span className="text-sm text-neutral-500">{note}</span>
            </div>
          ))}
        </div>
      )}
      <div className="border-t border-neutral-200 bg-neutral-50 px-4 py-4">
        <p className="text-sm text-neutral-600">
          {sessionId
            ? localGuardMode
              ? "Connected to the local guard."
              : "Polling for live Codex tool-call proposals."
            : "Start a session to listen for Codex tool-call proposals."}
        </p>
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
        <span className={`h-2.5 w-2.5 rounded-full ${riskDot[risk]}`} />
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
      <span className={`w-fit rounded-full border px-2.5 py-1 text-xs font-semibold ${statusChip[gate.status]}`}>
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
        <PanelTitle eyebrow="Inspector" title="No Action Selected" />
        <p className="mt-4 text-sm leading-6 text-neutral-600">
          Start supervision to inspect risk, trajectory, drift, policy, and approval controls.
        </p>
        <div className="mt-6 grid gap-2">
          <Fact label="Review Mode" value="Pending Gate" />
          <Fact label="Primary Surface" value="Slack + Console" />
          <Fact label="Ledger" value="Postgres Backed" />
        </div>
      </aside>
    );
  }

  const card = gate.intelligence_card;
  const disabled = gate.status !== "pending";
  return (
    <aside className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm xl:sticky xl:top-5 xl:self-start">
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Inspector</p>
      <div className="mt-3 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-xl font-semibold">{toolLabel(trace?.tool_name)}</h2>
          <p className="mt-1 truncate text-sm text-neutral-500">
            {gate.risk_assessment.affected_files[0] ?? "External State"}
          </p>
        </div>
        <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${statusChip[gate.status]}`}>
          {titleCase(gate.status)}
        </span>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-2">
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

      <label className="mt-5 block text-xs font-semibold uppercase tracking-wide text-neutral-500" htmlFor="decision-note">
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

function TrajectoryCard({ gate, trace, step }: { gate: Gate; trace: TraceEvent | undefined; step: number }) {
  return (
    <div className="grid gap-4 border border-neutral-200 bg-white p-4 md:grid-cols-[44px_minmax(0,1fr)_140px]">
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-neutral-950 text-sm font-semibold text-white">
        {step}
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <RiskBadge risk={gate.risk_assessment.risk_level} />
          <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusChip[gate.status]}`}>
            {titleCase(gate.status)}
          </span>
        </div>
        <h3 className="mt-3 truncate text-base font-semibold">
          {toolLabel(trace?.tool_name)} on {gate.risk_assessment.affected_files[0] ?? "External State"}
        </h3>
        <p className="mt-2 text-sm leading-6 text-neutral-600">
          {gate.intelligence_card?.trajectory_preview ?? "No trajectory preview available."}
        </p>
      </div>
      <div className="border-t border-neutral-200 pt-3 md:border-l md:border-t-0 md:pl-4 md:pt-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Confidence</p>
        <p className="mt-1 text-2xl font-semibold">
          {Math.round((gate.intelligence_card?.confidence ?? 0) * 100)}%
        </p>
      </div>
    </div>
  );
}

function TimelinePanel({
  traces,
  compact = false,
  frameless = false,
}: {
  traces: TraceEvent[];
  compact?: boolean;
  frameless?: boolean;
}) {
  const content = (
    <>
      {!frameless ? <PanelTitle eyebrow="Trace Capture" title="Execution Timeline" small /> : null}
      <div className={frameless ? "flex flex-col gap-3" : "mt-4 flex flex-col gap-3"}>
        {traces.length === 0 ? (
          <p className="text-sm text-neutral-500">No intercepted tool calls yet.</p>
        ) : (
          traces.map((trace, index) => (
            <div key={trace.id} className="border-l-2 border-neutral-300 pl-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Step {index + 1} / {toolLabel(trace.tool_name)}
              </p>
              <p className={`mt-1 text-sm text-neutral-700 ${compact ? "leading-5" : "leading-6"}`}>
                {trace.stated_reason}
              </p>
            </div>
          ))
        )}
      </div>
    </>
  );

  if (frameless) return content;
  return <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">{content}</section>;
}

function AnalyticsPanel({
  analytics,
  trustScore,
  compact = false,
}: {
  analytics: LedgerAnalytics | null;
  trustScore: number | null;
  compact?: boolean;
}) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <PanelTitle eyebrow="Audit Intelligence" title="Ledger Analytics" small />
        <p className="text-2xl font-semibold leading-none">{trustScore === null ? "--" : `${trustScore}%`}</p>
      </div>
      <div className={`mt-4 grid gap-4 ${compact ? "" : "md:grid-cols-2 xl:grid-cols-1"}`}>
        <BucketList title="Approval Patterns" buckets={analytics?.approval_patterns ?? []} />
        <BucketList title="Risk Distribution" buckets={analytics?.risk_distribution ?? []} />
      </div>
    </section>
  );
}

function Panel({ children }: { children: ReactNode }) {
  return <section className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">{children}</section>;
}

function PanelHeader({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="border-b border-neutral-300 pb-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{eyebrow}</p>
      <div className="mt-1 grid gap-3 xl:grid-cols-[220px_minmax(0,1fr)] xl:items-end">
        <h2 className="text-2xl font-semibold leading-tight">{title}</h2>
        <p className="max-w-3xl text-sm leading-6 text-neutral-600">{body}</p>
      </div>
    </div>
  );
}

function PanelTitle({
  eyebrow,
  title,
  body,
  small = false,
}: {
  eyebrow: string;
  title: string;
  body?: string;
  small?: boolean;
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{eyebrow}</p>
      <h2 className={`mt-1 font-semibold leading-tight ${small ? "text-lg" : "text-xl"}`}>{title}</h2>
      {body ? <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-600">{body}</p> : null}
    </div>
  );
}

function EmptyPanel({
  title,
  body,
  action,
  onAction,
}: {
  title: string;
  body: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <div className="mt-5 border border-dashed border-neutral-300 bg-neutral-50 p-5">
      <p className="font-semibold">{title}</p>
      <p className="mt-2 text-sm leading-6 text-neutral-600">{body}</p>
      <button
        onClick={onAction}
        className="mt-4 h-10 rounded-md bg-neutral-950 px-4 text-sm font-semibold text-white hover:bg-neutral-800"
      >
        {action}
      </button>
    </div>
  );
}

function SurfaceStep({ label, title, body }: { label: string; title: string; body: string }) {
  return (
    <div className="border border-neutral-200 bg-neutral-50 p-4">
      <p className="flex h-7 w-7 items-center justify-center rounded-full bg-neutral-950 text-xs font-semibold text-white">
        {label}
      </p>
      <p className="mt-3 text-sm font-semibold">{title}</p>
      <p className="mt-1 text-sm leading-5 text-neutral-600">{body}</p>
    </div>
  );
}

function LedgerRow({ label, title, body }: { label: string; title: string; body: string }) {
  return (
    <div className="grid gap-3 border border-neutral-200 bg-white p-4 md:grid-cols-[140px_minmax(0,1fr)]">
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</p>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{title}</p>
        <p className="mt-1 line-clamp-2 text-sm leading-6 text-neutral-600">{body}</p>
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-neutral-200 bg-neutral-50 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-neutral-950">{value}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-5 border-t border-neutral-200 pt-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{title}</p>
      <div className="mt-2 text-sm leading-6 text-neutral-700">{children}</div>
    </section>
  );
}

function BucketList({ title, buckets }: { title: string; buckets: CountBucket[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{title}</p>
      <div className="mt-2 flex flex-col gap-2">
        {buckets.length === 0 ? (
          <p className="text-sm text-neutral-500">No records yet.</p>
        ) : (
          buckets.map((bucket) => (
            <div key={bucket.name} className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate text-neutral-700">{titleCase(bucket.name)}</span>
              <span className="font-semibold">{bucket.count}</span>
            </div>
          ))
        )}
      </div>
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
  const styles = {
    neutral: "border-neutral-200",
    green: "border-emerald-300",
    sky: "border-sky-300",
    red: "border-red-300",
  };
  return (
    <div className={`rounded-lg border bg-white px-4 py-3 shadow-sm ${styles[accent]}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-2 truncate text-2xl font-semibold leading-none">{value}</p>
    </div>
  );
}

function Notice({ tone, children }: { tone: "blue" | "red"; children: ReactNode }) {
  const styles = {
    blue: "border-sky-200 bg-sky-50 text-sky-900",
    red: "border-red-200 bg-red-50 text-red-800",
  };
  return <div className={`border px-4 py-3 text-sm ${styles[tone]}`}>{children}</div>;
}

function RiskBadge({ risk }: { risk: RiskLevel }) {
  return <span className={`w-fit rounded-full border px-2.5 py-1 text-xs font-semibold ${riskChip[risk]}`}>{titleCase(risk)}</span>;
}

function NavItem({
  label,
  active = false,
  onClick,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-2 text-left transition ${
        active ? "bg-white text-neutral-950" : "text-neutral-400 hover:bg-neutral-900 hover:text-white"
      }`}
    >
      {label}
    </button>
  );
}

function StatusLine({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-wide text-neutral-500">{label}</p>
        <p className="truncate text-sm text-neutral-200">{value}</p>
      </div>
      <span className={`h-2 w-2 shrink-0 rounded-full ${ok ? "bg-emerald-400" : "bg-amber-400"}`} />
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
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${styles[tone]}`}>{label}</span>;
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

function isLocalApi(apiUrl: string) {
  return /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?/.test(apiUrl);
}
