"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Ban,
  BarChart3,
  Bell,
  Blocks,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Copy,
  Edit3,
  FileText,
  GitBranch,
  Info,
  Network,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Terminal,
  Trash2,
  XCircle,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
  Position,
} from "@xyflow/react";

import type {
  CountBucket,
  DemoResponse,
  ExplainMoreResponse,
  Gate,
  GateQuestionResponse,
  GateStatus,
  HealthState,
  LedgerAnalytics,
  PolicyConfigResponse,
  PolicyRule,
  PolicyTestResponse,
  RiskLevel,
  SessionSummary,
  SlackSendResult,
  TraceEvent,
  View,
} from "../types";
import {
  formatPercent,
  gateTarget,
  healthLabel,
  isInspectionGate,
  isInspectionTrace,
  riskChip,
  riskDot,
  sessionLabel,
  shortId,
  statusChip,
  summarizeTrace,
  titleCase,
  toolLabel,
} from "../utils";

type GateRow = {
  id: string;
  risk: RiskLevel;
  action: string;
  target: string;
  policy: string;
  status: GateStatus;
  confidence: number;
  gate: Gate;
  trace?: TraceEvent;
};

const navItems: { id: View; label: string; icon: ReactNode }[] = [
  { id: "review", label: "Review Queue", icon: <ClipboardList size={16} /> },
  { id: "trajectory", label: "Trajectory", icon: <GitBranch size={16} /> },
  { id: "policies", label: "Policy Ledger", icon: <SlidersHorizontal size={16} /> },
  { id: "slack", label: "Slack Surface", icon: <Bell size={16} /> },
  { id: "audit", label: "Audit Events", icon: <FileText size={16} /> },
];

const chartColors: Record<string, string> = {
  low: "#10b981",
  medium: "#f59e0b",
  high: "#ea580c",
  critical: "#dc2626",
  pending: "#0ea5e9",
  approved: "#10b981",
  blocked: "#dc2626",
  modified: "#8b5cf6",
  auto_executed: "#737373",
};

export function AppShell({
  activeView,
  onView,
  health,
  apiHost,
  recentSessions,
  activeSessionId,
  pinnedSessionId,
  slackChannel,
  slackLoading,
  onSwitchSession,
  onFollowLatest,
  onSlackChannel,
  onSendSlack,
  children,
}: {
  activeView: View;
  onView: (view: View) => void;
  health: HealthState;
  apiHost: string;
  recentSessions: SessionSummary[];
  activeSessionId: string | null;
  pinnedSessionId: string | null;
  slackChannel: string;
  slackLoading: boolean;
  onSwitchSession: (sessionId: string) => void;
  onFollowLatest: () => void;
  onSlackChannel: (value: string) => void;
  onSendSlack: () => void;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("agentlens-sidebar-collapsed");
      if (saved) setCollapsed(saved === "true");
    } catch {}
  }, []);
  useEffect(() => {
    try {
      window.localStorage.setItem("agentlens-sidebar-collapsed", String(collapsed));
    } catch {}
  }, [collapsed]);

  return (
    <main className="min-h-screen bg-[#f4f4f1] text-neutral-950">
      <div
        className={`grid min-h-screen transition-all duration-200 ${
          collapsed ? "lg:grid-cols-[72px_minmax(0,1fr)]" : "lg:grid-cols-[276px_minmax(0,1fr)]"
        }`}
      >
        <aside className="sticky top-0 hidden h-screen flex-col border-r border-neutral-800 bg-neutral-950 text-white lg:flex">
          <div
            className={`flex items-center border-b border-neutral-800 ${
              collapsed ? "justify-center py-5 px-1.5" : "justify-between px-6 py-5"
            }`}
          >
            {collapsed ? (
              <button
                onClick={() => setCollapsed(false)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-neutral-700 bg-neutral-900 text-white transition hover:bg-neutral-800"
                aria-label="Expand sidebar"
                title="Expand sidebar"
              >
                <ShieldCheck size={18} />
              </button>
            ) : (
              <>
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-neutral-700 bg-neutral-900">
                    <ShieldCheck size={18} />
                  </div>
                  <div>
                    <p className="text-lg font-semibold leading-none">AgentLens</p>
                    <p className="mt-2 text-xs uppercase tracking-wide text-neutral-500">Session Ledger</p>
                  </div>
                </div>
                <button
                  onClick={() => setCollapsed(true)}
                  className="flex h-8 w-8 items-center justify-center rounded-md text-neutral-400 transition hover:bg-neutral-900 hover:text-white"
                  aria-label="Collapse sidebar"
                  title="Collapse sidebar"
                >
                  <ChevronLeft size={16} />
                </button>
              </>
            )}
          </div>
          <nav
            className={`flex flex-1 flex-col gap-1 overflow-y-auto py-4 text-sm ${
              collapsed ? "px-2" : "px-3"
            }`}
          >
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onView(item.id)}
                className={`flex items-center gap-3 rounded-md py-2.5 text-left transition ${
                  collapsed ? "w-full justify-center px-2" : "px-3"
                } ${
                  activeView === item.id
                    ? "bg-white text-neutral-950"
                    : "text-neutral-400 hover:bg-neutral-900 hover:text-white"
                }`}
                title={collapsed ? item.label : undefined}
              >
                {item.icon}
                {!collapsed ? <span>{item.label}</span> : null}
              </button>
            ))}
          </nav>
          <div className={`border-t border-neutral-800 ${collapsed ? "p-3" : "p-4"}`}>
            <StatusLine label="Backend" value={healthLabel(health)} ok={health === "online"} collapsed={collapsed} />
            <StatusLine label="Primary Surface" value="Codex Native TUI" ok collapsed={collapsed} />
            <StatusLine label="Ambient Surface" value="Slack Ready" ok collapsed={collapsed} />
          </div>
        </aside>

        <section className="min-w-0">
          <header className="border-b border-neutral-200 bg-white">
            <div className="mx-auto flex max-w-[1720px] flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between lg:flex-wrap xl:px-8">
              <div className="min-w-0">
                <h1 className="text-[26px] font-semibold leading-tight tracking-normal">
                  Agent Session Ledger
                </h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-neutral-600">
                  Replay Codex actions, inspect risk evidence, and explain every human decision.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2 w-full lg:w-auto">
                <select
                  value={activeSessionId ?? ""}
                  onChange={(event) => onSwitchSession(event.target.value)}
                  className="h-10 w-full sm:w-[260px] rounded-md border border-neutral-300 bg-white px-3 text-sm font-medium outline-none focus:border-neutral-950 text-ellipsis"
                  aria-label="Active AgentLens session"
                >
                  <option value="" disabled>
                    No active session
                  </option>
                  {recentSessions.map((session) => (
                    <option key={session.id} value={session.id}>
                      {sessionLabel(session)}
                    </option>
                  ))}
                </select>
                <button
                  onClick={onFollowLatest}
                  className={`h-10 w-full sm:w-[100px] whitespace-nowrap rounded-md border px-3 text-sm font-semibold ${
                    pinnedSessionId
                      ? "border-neutral-950 bg-neutral-950 text-white hover:bg-neutral-800"
                      : "border-neutral-300 bg-white text-neutral-500"
                  }`}
                >
                  {pinnedSessionId ? "Follow Latest" : "Following"}
                </button>
                <input
                  value={slackChannel}
                  onChange={(event) => onSlackChannel(event.target.value)}
                  className="h-10 w-full sm:w-[140px] rounded-md border border-neutral-300 bg-white px-3 text-sm font-medium outline-none focus:border-neutral-950"
                  aria-label="Slack channel ID"
                />
                <button
                  onClick={onSendSlack}
                  disabled={slackLoading}
                  className="h-10 w-full sm:w-auto px-4 whitespace-nowrap rounded-md border border-neutral-300 bg-white text-sm font-semibold text-neutral-900 hover:border-neutral-950 disabled:cursor-not-allowed disabled:text-neutral-400 text-center"
                >
                  {slackLoading ? "Sending" : "Send To Slack"}
                </button>
              </div>
            </div>
          </header>

          <div className="mx-auto flex max-w-[1720px] flex-col gap-5 px-5 py-5 xl:px-8">
            {children}
          </div>
        </section>
      </div>
    </main>
  );
}

export function ReviewLedger({
  demo,
  gates,
  traces,
  selectedGate,
  traceByProposal,
  analytics,
  trustScore,
  apiUrl,
  localGuardMode,
  decisionNote,
  explain,
  explainLoading,
  explainError,
  onSelectGate,
  onDecisionNote,
  onDecision,
  onExplain,
}: {
  demo: DemoResponse | null;
  gates: Gate[];
  traces: TraceEvent[];
  selectedGate: Gate | null;
  traceByProposal: Map<string, TraceEvent>;
  analytics: LedgerAnalytics | null;
  trustScore: number | null;
  apiUrl: string;
  localGuardMode: boolean;
  decisionNote: string;
  explain: ExplainMoreResponse | null;
  explainLoading: boolean;
  explainError: string | null;
  onSelectGate: (id: string) => void;
  onDecisionNote: (value: string) => void;
  onDecision: (gate: Gate, action: "approve" | "block" | "modify") => Promise<void>;
  onExplain: (gate: Gate) => Promise<void>;
}) {
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_480px]">
      <div className="flex min-w-0 flex-col gap-5">
        <SectionHeader
          eyebrow="Session Ledger"
          title="Decision Queue"
          body={
            demo
              ? demo.session.original_instruction
              : "AgentLens is connected and waiting for Codex activity."
          }
        />
        {gates.length === 0 ? (
          <EmptyQueue sessionId={demo?.session.id ?? null} apiUrl={apiUrl} localGuardMode={localGuardMode} />
        ) : (
          <GateTable
            gates={gates}
            selectedGate={selectedGate}
            traceByProposal={traceByProposal}
            onSelectGate={onSelectGate}
          />
        )}
        <TimelineAnalyticsTabs traces={traces} gates={gates} analytics={analytics} trustScore={trustScore} />
      </div>

      <GateInspector
        gate={selectedGate}
        trace={selectedGate ? traceByProposal.get(selectedGate.proposal_id) : undefined}
        apiUrl={apiUrl}
        decisionNote={decisionNote}
        explain={explain}
        explainLoading={explainLoading}
        explainError={explainError}
        onDecisionNote={onDecisionNote}
        onDecision={onDecision}
        onExplain={onExplain}
      />
    </section>
  );
}

export function GateTable({
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
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filterText, setFilterText] = useState("");

  const inspectionGates = gates.filter((gate) =>
    isInspectionGate(gate, traceByProposal.get(gate.proposal_id)),
  );

  const filteredGates = useMemo(() => {
    if (!filterText.trim()) return gates;
    const query = filterText.toLowerCase();
    return gates.filter((gate) => {
      const trace = traceByProposal.get(gate.proposal_id);
      const actionLabel = toolLabel(trace?.tool_name).toLowerCase();
      const targetLabel = gateTarget(gate, trace).toLowerCase();
      const summaryLabel = (gate.intelligence_card?.summary ?? trace?.stated_reason ?? "").toLowerCase();
      const policyLabel = (gate.policy_decision.matched_policy ?? "Semantic Risk").toLowerCase();
      const statusLabel = gate.status.toLowerCase();

      return (
        actionLabel.includes(query) ||
        targetLabel.includes(query) ||
        summaryLabel.includes(query) ||
        policyLabel.includes(query) ||
        statusLabel.includes(query)
      );
    });
  }, [gates, filterText, traceByProposal]);

  const rows = useMemo<GateRow[]>(
    () =>
      filteredGates
        .filter((gate) => !isInspectionGate(gate, traceByProposal.get(gate.proposal_id)))
        .map((gate) => {
          const trace = traceByProposal.get(gate.proposal_id);
          return {
            id: gate.id,
            risk: gate.risk_assessment.risk_level,
            action: toolLabel(trace?.tool_name),
            target: gateTarget(gate, trace),
            policy: gate.policy_decision.matched_policy ?? "Semantic Risk",
            status: gate.status,
            confidence: gate.intelligence_card?.confidence ?? 0,
            gate,
            trace,
          };
        })
        .sort((a, b) => Number(b.status === "pending") - Number(a.status === "pending")),
    [filteredGates, traceByProposal],
  );

  const showInspectionBatch = useMemo(() => {
    if (inspectionGates.length === 0) return false;
    if (!filterText.trim()) return true;
    const query = filterText.toLowerCase();
    return (
      "auto-executed inspection batch".includes(query) ||
      "collapsed".includes(query) ||
      "inspection".includes(query)
    );
  }, [inspectionGates, filterText]);

  const columns = useMemo<ColumnDef<GateRow>[]>(
    () => [
      {
        accessorKey: "risk",
        header: "Risk",
        cell: ({ row }) => <RiskCell risk={row.original.risk} />,
      },
      {
        accessorKey: "target",
        header: "Action",
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-neutral-950">
              {row.original.action} on {row.original.target}
            </p>
            <p className="mt-1 line-clamp-1 text-xs leading-5 text-neutral-500">
              {row.original.gate.intelligence_card?.summary
                ?? row.original.trace?.stated_reason
                ?? "No summary available."}
            </p>
          </div>
        ),
      },
      {
        accessorKey: "policy",
        header: "Policy",
        cell: ({ row }) => <span className="text-sm text-neutral-600">{row.original.policy}</span>,
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        accessorKey: "confidence",
        header: "Confidence",
        cell: ({ row }) => (
          <span className="text-sm font-semibold">{Math.round(row.original.confidence * 100)}%</span>
        ),
      },
    ],
    [],
  );
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <section className="overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-200 px-5 py-4 bg-white rounded-t-lg">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Gate Queue</p>
          <p className="mt-0.5 text-sm text-neutral-500">Pending decisions stay visible until resolved.</p>
        </div>
        <div className="relative w-full sm:w-64">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-neutral-400">
            <Search size={16} />
          </span>
          <input
            type="text"
            placeholder="Search decisions..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="w-full h-9 pl-9 pr-4 rounded-md border border-neutral-300 bg-neutral-50 text-sm font-medium text-neutral-900 placeholder-neutral-400 outline-none focus:border-neutral-950 focus:bg-white transition"
          />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] border-collapse text-left">
          <colgroup>
            <col className="w-[120px]" />
            <col className="min-w-0" />
            <col className="w-[150px]" />
            <col className="w-[130px]" />
            <col className="w-[110px]" />
          </colgroup>
          <thead className="bg-neutral-50 text-xs font-semibold uppercase tracking-wide text-neutral-500 border-b border-neutral-200">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="px-4 py-3 text-left">
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {showInspectionBatch ? (
              <tr className="border-b border-neutral-100 bg-neutral-50/40">
                <td className="px-4 py-4 align-middle">
                  <RiskCell risk="low" />
                </td>
                <td className="px-4 py-4 align-middle min-w-0">
                  <div>
                    <p className="text-sm font-semibold text-neutral-900">Auto-Executed Inspection Batch</p>
                    <p className="mt-1 text-xs text-neutral-500">
                      {inspectionGates.length} read-only shell/file inspection calls collapsed.
                    </p>
                  </div>
                </td>
                <td className="px-4 py-4 align-middle">
                  <span className="text-sm text-neutral-500">-</span>
                </td>
                <td className="px-4 py-4 align-middle">
                  <StatusBadge status="auto_executed" />
                </td>
                <td className="px-4 py-4 align-middle">
                  <span className="text-sm font-semibold text-neutral-700">Low</span>
                </td>
              </tr>
            ) : null}
            {table.getRowModel().rows.length === 0 && !showInspectionBatch ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-neutral-500">
                  No records match search criteria.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => onSelectGate(row.original.id)}
                  className={`cursor-pointer border-b border-neutral-100 transition last:border-b-0 hover:bg-neutral-50 ${
                    selectedGate?.id === row.original.id ? "bg-sky-50/70 shadow-[inset_3px_0_0_#0ea5e9]" : ""
                  }`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-4 align-middle">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function GateInspector({
  gate,
  trace,
  apiUrl,
  decisionNote,
  explain,
  explainLoading,
  explainError,
  onDecisionNote,
  onDecision,
  onExplain,
}: {
  gate: Gate | null;
  trace: TraceEvent | undefined;
  apiUrl: string;
  decisionNote: string;
  explain: ExplainMoreResponse | null;
  explainLoading: boolean;
  explainError: string | null;
  onDecisionNote: (value: string) => void;
  onDecision: (gate: Gate, action: "approve" | "block" | "modify") => Promise<void>;
  onExplain: (gate: Gate) => Promise<void>;
}) {
  if (!gate) {
    return (
      <aside className="flex flex-col justify-between rounded-xl border border-neutral-200 bg-white p-6 shadow-sm min-h-[400px]">
        <div className="flex flex-col items-center justify-center flex-1 py-8 text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-neutral-50 border border-neutral-200 text-neutral-400">
            <ShieldCheck size={22} />
          </div>
          <h3 className="text-base font-bold text-neutral-900 tracking-tight">Active Inspector</h3>
          <p className="mt-2 max-w-xs text-xs text-neutral-500 leading-relaxed">
            Select any proposal gate from the queue on the left to analyze trajectory, audit intelligence, and verify policies.
          </p>
        </div>
        <div className="border-t border-neutral-100 pt-5 space-y-2.5">
          <div className="flex items-center justify-between text-xs py-1.5 border-b border-neutral-50">
            <span className="font-semibold text-neutral-400 uppercase tracking-wider">Review Surface</span>
            <span className="font-bold text-neutral-800">Codex Native + Slack</span>
          </div>
          <div className="flex items-center justify-between text-xs py-1.5 border-b border-neutral-50">
            <span className="font-semibold text-neutral-400 uppercase tracking-wider">Ledger Mode</span>
            <span className="font-bold text-neutral-800">Pinned Sessions</span>
          </div>
          <div className="flex items-center justify-between text-xs py-1.5">
            <span className="font-semibold text-neutral-400 uppercase tracking-wider">Strict Path</span>
            <span className="font-bold text-neutral-800 text-right">App-Server Proxy</span>
          </div>
        </div>
      </aside>
    );
  }

  const [tab, setTab] = useState<InspectorTab>("summary");
  const card = gate.intelligence_card;
  const canDecide = gate.status === "pending";

  return (
    <aside className="sticky top-5 flex max-h-[calc(100vh-1.5rem)] flex-col overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-neutral-200 p-5 pb-4">
        <PanelTitle
          eyebrow="Inspector"
          title={toolLabel(trace?.tool_name)}
          body={gateTarget(gate, trace)}
          icon={<ShieldAlert size={18} />}
        />
        <StatusBadge status={gate.status} />
      </div>

      <div className="flex gap-1 border-b border-neutral-100 px-5 pt-3 bg-neutral-50/30">
        {inspectorTabs.map((item) => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            className={`border-b-2 px-3 pb-2.5 text-xs font-bold uppercase tracking-wider transition outline-none ${
              tab === item.id
                ? "border-neutral-900 text-neutral-900"
                : "border-transparent text-neutral-400 hover:text-neutral-700"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {tab === "summary" ? (
          <>
            <div className="grid grid-cols-3 gap-2">
              <Fact label="Risk" value={titleCase(gate.risk_assessment.risk_level)} />
              <Fact label="Blast" value={titleCase(gate.risk_assessment.blast_radius)} />
              <Fact label="Confidence" value={formatPercent(card?.confidence)} />
            </div>
            <Section title="Recommendation">
              <p>{card?.summary ?? "No intelligence summary available."}</p>
            </Section>
            <Section title="Policy Match">
              <div className="grid gap-2">
                <Fact label="Decision" value={titleCase(gate.policy_decision.action)} />
                <Fact label="Matched Policy" value={gate.policy_decision.matched_policy ?? "Semantic Risk"} />
                <p className="text-sm leading-6 text-neutral-600">{gate.policy_decision.reason}</p>
              </div>
            </Section>
          </>
        ) : null}

        {tab === "trajectory" ? (
          <>
            <Section title="Trajectory">
              <p>{card?.trajectory_preview ?? "No trajectory preview available."}</p>
              {card?.full_trajectory?.next_steps?.length ? (
                <ol className="mt-3 flex flex-col gap-2">
                  {card.full_trajectory.next_steps.map((step) => (
                    <li key={`${step.step}-${step.action}`} className="rounded-md border border-neutral-200 bg-neutral-50 p-3">
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                        Step {step.step}
                      </span>
                      <p className="mt-1 text-sm font-semibold text-neutral-950">{step.action}</p>
                      <p className="mt-1 text-xs leading-5 text-neutral-600">{step.rationale}</p>
                    </li>
                  ))}
                </ol>
              ) : null}
            </Section>
            <Section title="Dependency Graph">
              <DependencyGraph gate={gate} />
            </Section>
          </>
        ) : null}

        {tab === "evidence" ? (
          <>
            <Section title="Why Confidence Changed">
              <ConfidenceFactors gate={gate} />
            </Section>
            <Section title="Risk Evidence">
              <ul className="flex flex-col gap-2">
                {gate.risk_assessment.evidence.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </Section>
            {gate.human_reason ? (
              <Section title="Decision History">
                <p>{gate.human_reason}</p>
              </Section>
            ) : null}
          </>
        ) : null}

        {tab === "explain" ? (
          <>
            <button
              onClick={() => onExplain(gate)}
              className="h-10 w-full rounded-md border border-neutral-300 text-sm font-semibold text-neutral-900 hover:border-neutral-950"
            >
              {explainLoading ? "Loading Explanation" : "Explain More"}
            </button>
            {explainError ? <p className="mt-2 text-xs leading-5 text-red-700">{explainError}</p> : null}
            {explain ? <ExplainMorePanel explain={explain} trace={trace} apiUrl={apiUrl} /> : null}
          </>
        ) : null}
      </div>

      <div className="border-t border-neutral-200 p-5">
        {canDecide ? (
          <>
            <label className="block text-xs font-semibold uppercase tracking-wide text-neutral-500" htmlFor="decision-note">
              Gate Decision Note
            </label>
            <input
              id="decision-note"
              value={decisionNote}
              onChange={(event) => onDecisionNote(event.target.value)}
              className="mt-2 h-10 w-full rounded-md border border-neutral-300 px-3 text-sm outline-none focus:border-neutral-950"
            />
            <div className="mt-4 grid grid-cols-3 gap-2">
              <DecisionButton tone="approve" onClick={() => onDecision(gate, "approve")}>Approve</DecisionButton>
              <DecisionButton tone="block" onClick={() => onDecision(gate, "block")}>Block</DecisionButton>
              <DecisionButton tone="modify" onClick={() => onDecision(gate, "modify")}>Modify</DecisionButton>
            </div>
            <p className="mt-3 text-xs leading-5 text-neutral-500">
              In app-server proxy mode, Codex is waiting for this decision before the approval response is returned.
            </p>
          </>
        ) : (
          <p className="text-xs leading-5 text-neutral-500">
            This gate is resolved in the AgentLens ledger.
          </p>
        )}
      </div>
    </aside>
  );
}

const inspectorTabs = [
  { id: "summary", label: "Summary" },
  { id: "trajectory", label: "Trajectory" },
  { id: "evidence", label: "Evidence" },
  { id: "explain", label: "Explain" },
] as const;
type InspectorTab = (typeof inspectorTabs)[number]["id"];

function ExplainMorePanel({ explain, trace, apiUrl }: { explain: ExplainMoreResponse; trace?: TraceEvent; apiUrl: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<GateQuestionResponse | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);

  async function askQuestion() {
    if (!question.trim()) return;
    setAsking(true);
    setAskError(null);
    try {
      const response = await fetch(`${apiUrl}/gates/${explain.gate_id}/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!response.ok) throw new Error(`Question failed with ${response.status}`);
      setAnswer((await response.json()) as GateQuestionResponse);
    } catch (error) {
      setAskError(error instanceof Error ? error.message : "Unable to answer question");
      setAnswer({
        gate_id: explain.gate_id,
        question,
        answer: answerExplainQuestion(question, explain),
        evidence: [],
        used_model_role: "client_fallback",
      });
    } finally {
      setAsking(false);
    }
  }

  return (
    <section className="mt-5 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
      <div className="flex items-center gap-2">
        <Info size={16} className="text-sky-700" />
        <p className="text-sm font-semibold">Expanded Explanation</p>
      </div>
      <p className="mt-3 text-sm leading-6 text-neutral-700">
        {explain.summary ?? explain.context_summary}
      </p>
      {explain.suggested_modification ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">Safer Modification</p>
          <p className="mt-1 text-sm leading-6 text-amber-950">{explain.suggested_modification}</p>
        </div>
      ) : null}
      <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-neutral-500" htmlFor="explain-question">
        Ask About This Gate
      </label>
      <input
        id="explain-question"
        value={question}
        onChange={(event) => {
          setQuestion(event.target.value);
          setAnswer(null);
          setAskError(null);
        }}
        placeholder="Why is this risky?"
        className="mt-2 h-10 w-full rounded-md border border-neutral-300 bg-white px-3 text-sm outline-none focus:border-neutral-950"
      />
      <button
        onClick={() => void askQuestion()}
        disabled={!question.trim() || asking}
        className="mt-2 h-9 rounded-md bg-neutral-950 px-3 text-xs font-semibold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {asking ? "Answering" : "Ask AgentLens"}
      </button>
      {askError ? <p className="mt-2 text-xs leading-5 text-amber-700">{askError}; showing fallback.</p> : null}
      {answer ? (
        <div className="mt-3 rounded-md border border-neutral-200 bg-white p-3 text-sm leading-6 text-neutral-700">
          <p>{answer.answer}</p>
          <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
            Source: {titleCase(answer.used_model_role)}
          </p>
          {answer.evidence.length ? (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-neutral-500">
              {answer.evidence.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : null}
        </div>
      ) : null}
      <details className="mt-4">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Raw Tool Payload
        </summary>
        <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-neutral-950 p-3 text-xs leading-5 text-neutral-100">
{JSON.stringify(
  {
    gate_id: explain.gate_id,
    tool_name: trace?.tool_name,
    stated_reason: trace?.stated_reason,
    params: trace?.params,
  },
  null,
  2,
)}
        </pre>
      </details>
    </section>
  );
}

export function DependencyGraph({ gate }: { gate: Gate }) {
  const evidence = gate.intelligence_card?.dependency_evidence ?? [];
  const primary = evidence[0];
  if (!primary) {
    return (
      <div className="rounded-md border border-dashed border-neutral-300 bg-neutral-50 p-3 text-sm text-neutral-600">
        No dependency references were recorded for this action.
      </div>
    );
  }
  const referenced = primary.referenced_by.slice(0, 8);
  const config = primary.config_references.slice(0, 4);
  const nodes: Node[] = [
    {
      id: "target",
      position: { x: 260, y: 90 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      data: { label: primary.path },
      className: "rounded-md border border-neutral-950 bg-white px-3 py-2 text-xs font-semibold shadow-sm",
    },
    ...referenced.map((path, index) => ({
      id: `code-${index}`,
      position: { x: 20, y: index * 62 },
      sourcePosition: Position.Right,
      data: { label: path },
      className: "rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-950",
    })),
    ...config.map((path, index) => ({
      id: `config-${index}`,
      position: { x: 520, y: index * 62 },
      targetPosition: Position.Left,
      data: { label: path },
      className: "rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950",
    })),
  ];
  const edges: Edge[] = [
    ...referenced.map((_, index) => ({ id: `code-edge-${index}`, source: `code-${index}`, target: "target" })),
    ...config.map((_, index) => ({ id: `config-edge-${index}`, source: "target", target: `config-${index}` })),
  ];
  return (
    <div>
      <div className="h-64 overflow-hidden rounded-md border border-neutral-200 bg-white">
        <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}>
          <Background gap={18} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <p className="mt-2 text-xs leading-5 text-neutral-500">{primary.summary}</p>
      {primary.referenced_by.length + primary.config_references.length > referenced.length + config.length ? (
        <p className="mt-1 text-xs font-semibold text-neutral-600">
          +{primary.referenced_by.length + primary.config_references.length - referenced.length - config.length} more references.
        </p>
      ) : null}
    </div>
  );
}

export function LedgerAnalyticsPanel({
  analytics,
  trustScore,
}: {
  analytics: LedgerAnalytics | null;
  trustScore: number | null;
}) {
  return (
    <Panel>
      <div className="flex items-baseline justify-between gap-3">
        <PanelTitle eyebrow="Audit Intelligence" title="Ledger Analytics" icon={<BarChart3 size={18} />} />
        <p className="text-3xl font-semibold leading-none">{trustScore === null ? "--" : `${trustScore}%`}</p>
      </div>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <ChartBlock title="Approval Patterns">
          <BucketBarChart buckets={analytics?.approval_patterns ?? []} />
        </ChartBlock>
        <ChartBlock title="Risk Distribution">
          <BucketBarChart buckets={analytics?.risk_distribution ?? []} />
        </ChartBlock>
      </div>
      <div className="mt-5 rounded-md border border-neutral-200 bg-neutral-50 p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Trust Score Basis</p>
        <p className="mt-2 text-sm leading-6 text-neutral-700">
          {analytics
            ? `${analytics.trust_score.auto_executed} actions auto-executed, ${analytics.trust_score.human_interventions} required human intervention.`
            : "No actions recorded yet."}
        </p>
      </div>
    </Panel>
  );
}

function BucketBarChart({ buckets }: { buckets: CountBucket[] }) {
  if (buckets.length === 0) {
    return <p className="flex h-full items-center text-sm text-neutral-500">No records yet.</p>;
  }
  const data = buckets.map((bucket) => ({ ...bucket, label: titleCase(bucket.name) }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} layout="vertical" margin={{ left: 4, right: 12, top: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e5e5" />
        <XAxis type="number" allowDecimals={false} hide />
        <YAxis type="category" dataKey="label" width={92} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey="count" radius={[0, 4, 4, 0]}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={chartColors[entry.name] ?? "#171717"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ConfidenceFactors({ gate }: { gate: Gate }) {
  const factors = gate.intelligence_card?.confidence_evidence ?? [];
  if (factors.length === 0) {
    return <p>No confidence factors were recorded.</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      {factors.map((item) => (
        <div key={`${item.label}-${item.detail}`} className="grid grid-cols-[58px_minmax(0,1fr)] gap-3">
          <span className={item.impact >= 0 ? "text-sm font-semibold text-emerald-700" : "text-sm font-semibold text-red-700"}>
            {item.impact >= 0 ? "+" : ""}
            {Math.round(item.impact * 100)}
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-neutral-950">{item.label}</span>
            <span className="block text-xs leading-5 text-neutral-600">{item.detail}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

export function TrajectoryView({
  gates,
  traces,
  traceByProposal,
}: {
  gates: Gate[];
  traces: TraceEvent[];
  traceByProposal: Map<string, TraceEvent>;
}) {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)] gap-6">
      <Panel>
        <PanelTitle
          eyebrow="Counterfactual Engine"
          title="Predicted Direction"
          icon={<GitBranch size={18} />}
        />
        <div className="mt-4">
          <p className="text-sm text-neutral-500 mb-4">
            Predicted future actions based on current prompt and state.
          </p>
          {gates.length === 0 ? (
            <EmptyState
              title="No trajectory yet"
              body="Use Codex normally. AgentLens will record trajectory once a gate appears."
            />
          ) : (
            <div className="grid gap-3">
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
        </div>
      </Panel>

      <TimelineLedger traces={traces} gates={gates} />
    </div>
  );
}

const policyInputClass = "mt-1 h-10 w-full min-w-0 rounded-md border border-neutral-300 bg-white px-3 text-sm font-medium normal-case tracking-normal text-neutral-900 outline-none transition focus:border-neutral-950 focus:ring-2 focus:ring-neutral-950/10";
const policyButtonFeedback = "inline-flex items-center justify-center rounded-md text-sm font-semibold transition duration-150 hover:-translate-y-px active:translate-y-0 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-neutral-950/15 disabled:pointer-events-none disabled:opacity-50";
const primaryPolicyButtonClass = `${policyButtonFeedback} h-9 bg-neutral-950 px-3 text-white hover:bg-neutral-800`;
const secondaryPolicyButtonClass = `${policyButtonFeedback} h-9 border border-neutral-300 bg-white px-3 text-neutral-900 hover:border-neutral-950 hover:bg-neutral-50`;
const savePolicyButtonClass = `${policyButtonFeedback} h-9 border border-emerald-300 bg-emerald-50 px-3 text-emerald-800 hover:border-emerald-500 hover:bg-emerald-100`;
const secondarySmallButtonClass = `${policyButtonFeedback} h-8 border border-neutral-300 bg-white px-2.5 text-xs text-neutral-900 hover:border-neutral-950 hover:bg-neutral-50`;
const dangerSmallButtonClass = `${policyButtonFeedback} h-8 border border-red-200 bg-red-50 px-2.5 text-xs text-red-700 hover:border-red-300 hover:bg-red-100`;
const headerIconButtonClass = "inline-flex h-8 w-8 items-center justify-center rounded-md border border-neutral-200 bg-white text-neutral-600 hover:border-neutral-400 hover:text-neutral-900 disabled:opacity-30 disabled:pointer-events-none transition shadow-sm hover:shadow active:scale-[0.98]";
const headerDangerButtonClass = "inline-flex h-8 w-8 items-center justify-center rounded-md border border-red-200 bg-red-50 text-red-600 hover:border-red-400 hover:bg-red-100 hover:text-red-700 disabled:opacity-30 disabled:pointer-events-none transition shadow-sm hover:shadow active:scale-[0.98]";

function policyCompareKey(policies: PolicyRule[]) {
  return JSON.stringify(
    policies.map((policy) => ({
      name: policy.name,
      action: policy.action,
      min_confidence: policy.min_confidence ?? null,
      condition: policy.condition ?? {},
    })),
  );
}

export function PolicyLedgerView({ gates, apiUrl }: { gates: Gate[]; apiUrl: string }) {
  const [config, setConfig] = useState<PolicyConfigResponse | null>(null);
  const [draftPolicies, setDraftPolicies] = useState<PolicyRule[]>([]);
  const [policyMessage, setPolicyMessage] = useState<string | null>(null);
  const [policyError, setPolicyError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testTool, setTestTool] = useState("fs.write");
  const [testTarget, setTestTarget] = useState("README.md");
  const [testConfidence, setTestConfidence] = useState("0.72");
  const [testRisk, setTestRisk] = useState<RiskLevel>("medium");
  const [testResult, setTestResult] = useState<PolicyTestResponse | null>(null);
  const dirty = useMemo(
    () => policyCompareKey(config?.policies ?? []) !== policyCompareKey(draftPolicies),
    [config?.policies, draftPolicies],
  );

  useEffect(() => {
    void loadPolicies();
  }, [apiUrl]);

  async function loadPolicies() {
    setPolicyError(null);
    try {
      const response = await fetch(`${apiUrl}/policies`);
      if (!response.ok) throw new Error(`Policy load failed with ${response.status}`);
      const body = (await response.json()) as PolicyConfigResponse;
      setConfig(body);
      setDraftPolicies(body.policies);
      setPolicyMessage(`Loaded ${body.policies.length} policy rule${body.policies.length === 1 ? "" : "s"}.`);
    } catch (error) {
      setPolicyError(error instanceof Error ? error.message : "Unable to load policies");
    }
  }

  async function savePolicies() {
    setSaving(true);
    setPolicyError(null);
    try {
      const response = await fetch(`${apiUrl}/policies`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ policies: draftPolicies }),
      });
      if (!response.ok) throw new Error(`Policy save failed with ${response.status}`);
      const body = (await response.json()) as PolicyConfigResponse;
      setConfig(body);
      setDraftPolicies(body.policies);
      setPolicyMessage(`Saved ${body.policies.length} policy rule${body.policies.length === 1 ? "" : "s"} to ${body.config_path}.`);
    } catch (error) {
      setPolicyError(error instanceof Error ? error.message : "Unable to save policies");
    } finally {
      setSaving(false);
    }
  }

  async function testDraftPolicies() {
    setPolicyError(null);
    try {
      const confidence = Number.parseFloat(testConfidence);
      const params = testTool === "shell.run"
        ? { command: testTarget }
        : testTool === "db.query"
          ? { query: testTarget }
          : { path: testTarget };
      const response = await fetch(`${apiUrl}/policies/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          policies: draftPolicies,
          risk_level: testRisk,
          proposal: {
            session_id: "policy_test",
            tool_name: testTool,
            params,
            confidence: Number.isFinite(confidence) ? confidence : null,
          },
        }),
      });
      if (!response.ok) throw new Error(`Policy test failed with ${response.status}`);
      setTestResult((await response.json()) as PolicyTestResponse);
    } catch (error) {
      setPolicyError(error instanceof Error ? error.message : "Unable to test policies");
    }
  }

  function updatePolicy(index: number, patch: Partial<PolicyRule>) {
    setDraftPolicies((current) => current.map((policy, itemIndex) => itemIndex === index ? { ...policy, ...patch } : policy));
  }

  function updateCondition(index: number, value: string) {
    try {
      const parsed = JSON.parse(value) as Record<string, unknown>;
      updatePolicy(index, { condition: parsed });
      setPolicyError(null);
    } catch {
      setPolicyError("Condition JSON is invalid. Fix it before saving.");
    }
  }

  function movePolicy(index: number, direction: -1 | 1) {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= draftPolicies.length) return;
    setDraftPolicies((current) => {
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(nextIndex, 0, item);
      return next;
    });
  }

  function addPolicy() {
    setDraftPolicies((current) => [
      ...current,
      {
        name: "New policy",
        condition: { path_contains: ["README.md"] },
        action: "require_approval",
        min_confidence: null,
      },
    ]);
  }

  const runtimeRows = gates.map((gate) => ({
    name: gate.policy_decision.matched_policy ?? "Semantic Risk Recommendation",
    condition: gate.policy_decision.reason,
    action: titleCase(gate.policy_decision.action),
    risk: gate.risk_assessment.risk_level,
    status: gate.status,
  }));

  return (
    <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,380px)]">
      <div className="min-w-0 space-y-5">
        {/* Runtime Matches Section (moved above Policy Management) */}
        <Panel>
          <PanelTitle
            eyebrow="Runtime Matches"
            title="Session Policy Ledger"
            body="These rows show how the current session matched configured rules or semantic risk fallback."
            icon={<BarChart3 size={18} />}
            small
          />
          <div className="mt-5 overflow-hidden rounded-lg border border-neutral-200">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left">
                <thead className="bg-neutral-50 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="border-b border-neutral-200 px-4 py-3">Rule</th>
                    <th className="border-b border-neutral-200 px-4 py-3">Condition</th>
                    <th className="border-b border-neutral-200 px-4 py-3">Decision</th>
                    <th className="border-b border-neutral-200 px-4 py-3">Risk</th>
                    <th className="border-b border-neutral-200 px-4 py-3">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {runtimeRows.length ? runtimeRows.map((row, index) => (
                    <tr key={`${row.name}-${index}`} className="border-b border-neutral-100 last:border-b-0">
                      <td className="px-4 py-4 text-sm font-semibold">{row.name}</td>
                      <td className="max-w-[360px] px-4 py-4 text-sm text-neutral-600">
                        <span className="line-clamp-2">{row.condition}</span>
                      </td>
                      <td className="px-4 py-4 text-sm font-medium">{row.action}</td>
                      <td className="px-4 py-4"><RiskBadge risk={row.risk} /></td>
                      <td className="px-4 py-4"><StatusBadge status={row.status} /></td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-sm text-neutral-500">
                        No runtime policy matches in this session yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </Panel>

        {/* Standing Rules (Policy Management) Section */}
        <Panel>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <PanelTitle
              eyebrow="Policy Management"
              title="Standing Rules"
              body="Edit ordered rules, test the draft against a sample action, then save back to agentlens.config.yaml."
              icon={<SlidersHorizontal size={18} />}
            />
            {dirty ? (
              <span className="inline-flex w-fit shrink-0 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
                Unsaved changes
              </span>
            ) : null}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button onClick={addPolicy} className={primaryPolicyButtonClass}>
              <Plus size={15} className="mr-1.5" />
              Create Policy
            </button>
            <button onClick={() => void loadPolicies()} className={secondaryPolicyButtonClass}>
              <RefreshCw size={15} className="mr-1.5" />
              Reload
            </button>
            <button
              onClick={() => void savePolicies()}
              disabled={!dirty || saving || Boolean(policyError?.includes("Condition JSON"))}
              className={savePolicyButtonClass}
            >
              <Save size={15} className="mr-1.5" />
              {saving ? "Saving" : "Save To Config"}
            </button>
          </div>
          {policyMessage ? <p className="mt-3 text-sm text-neutral-600">{policyMessage}</p> : null}
          {policyError ? <p className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{policyError}</p> : null}
          <div className="mt-5 space-y-3">
            {draftPolicies.map((policy, index) => (
              <article
                key={policy._localId || index}
                className="animate-slide-down-fade-in overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm hover:shadow transition duration-200"
              >
                {/* Card Header */}
                <div className="flex items-center justify-between border-b border-neutral-200 bg-neutral-50 px-4 py-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-neutral-200 text-xs font-bold text-neutral-700">
                      {index + 1}
                    </span>
                    <span className="text-xs font-bold uppercase tracking-wider text-neutral-600">
                      Policy Rule
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => movePolicy(index, -1)}
                      disabled={index === 0}
                      className={headerIconButtonClass}
                      title="Move Up"
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      onClick={() => movePolicy(index, 1)}
                      disabled={index === draftPolicies.length - 1}
                      className={headerIconButtonClass}
                      title="Move Down"
                    >
                      <ArrowDown size={14} />
                    </button>
                    <button
                      onClick={() => {
                        setDraftPolicies((current) => {
                          const copy = {
                            ...policy,
                            name: `${policy.name} Copy`,
                            _localId: Math.random().toString(36).substring(2, 9),
                          };
                          const next = [...current];
                          next.splice(index + 1, 0, copy);
                          return next;
                        });
                      }}
                      className={headerIconButtonClass}
                      title="Duplicate"
                    >
                      <Copy size={14} />
                    </button>
                    <button
                      onClick={() => setDraftPolicies((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                      className={headerDangerButtonClass}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {/* Card Body */}
                <div className="p-4 space-y-4">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <label className="flex flex-col text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      Name
                      <input
                        value={policy.name}
                        onChange={(event) => updatePolicy(index, { name: event.target.value })}
                        className={policyInputClass}
                      />
                    </label>
                    <label className="flex flex-col text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      Action
                      <select
                        value={policy.action}
                        onChange={(event) => updatePolicy(index, { action: event.target.value as PolicyRule["action"] })}
                        className={policyInputClass}
                      >
                        {(config?.supported_actions ?? ["auto_execute", "require_approval", "block_and_alert"]).map((action) => (
                          <option key={action} value={action}>{titleCase(action)}</option>
                        ))}
                      </select>
                    </label>
                    <label className="flex flex-col text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      Min Conf.
                      <input
                        value={policy.min_confidence ?? ""}
                        placeholder="optional"
                        onChange={(event) => updatePolicy(index, { min_confidence: event.target.value ? Number(event.target.value) : null })}
                        className={policyInputClass}
                      />
                    </label>
                  </div>

                  <label className="block text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                    Condition JSON
                    <textarea
                      defaultValue={JSON.stringify(policy.condition, null, 2)}
                      onBlur={(event) => updateCondition(index, event.target.value)}
                      className="mt-1 min-h-[80px] max-h-36 w-full resize-y rounded-md border border-neutral-300 bg-white p-3 font-mono text-xs normal-case tracking-normal outline-none transition focus:border-neutral-950 focus:ring-2 focus:ring-neutral-950/10"
                    />
                  </label>
                </div>
              </article>
            ))}
          </div>
        </Panel>
      </div>

      <aside className="min-w-0 xl:sticky xl:top-5 xl:self-start">
        <Panel>
          <PanelTitle
            eyebrow="Draft Test"
            title="Policy Simulator"
            body="Run the unsaved policy draft against a representative tool call."
            icon={<Search size={18} />}
            small
          />
          <div className="mt-5 grid gap-3">
            <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Tool
              <select value={testTool} onChange={(event) => setTestTool(event.target.value)} className={policyInputClass}>
                {["fs.read", "fs.write", "fs.delete", "shell.run", "db.query", "api.call", "git.status", "run_tests"].map((tool) => (
                  <option key={tool} value={tool}>{tool}</option>
                ))}
              </select>
            </label>
            <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Target Path / Command / Query
              <input value={testTarget} onChange={(event) => setTestTarget(event.target.value)} className={policyInputClass} />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Confidence
                <input value={testConfidence} onChange={(event) => setTestConfidence(event.target.value)} className={policyInputClass} />
              </label>
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Risk
                <select value={testRisk} onChange={(event) => setTestRisk(event.target.value as RiskLevel)} className={policyInputClass}>
                  {["low", "medium", "high", "critical"].map((risk) => <option key={risk} value={risk}>{titleCase(risk)}</option>)}
                </select>
              </label>
            </div>
            <button onClick={() => void testDraftPolicies()} className={primaryPolicyButtonClass}>Test Draft Policies</button>
            {testResult ? (
              <div className={`rounded-lg border p-4 transition duration-200 animate-slide-down-fade-in ${
                testResult.decision.action === "auto_execute"
                  ? "border-emerald-200 bg-emerald-50/50 text-emerald-950"
                  : testResult.decision.action === "require_approval"
                  ? "border-amber-200 bg-amber-50/50 text-amber-950"
                  : "border-red-200 bg-red-50/50 text-red-950"
              }`}>
                <div className="flex items-center gap-2">
                  {testResult.decision.action === "auto_execute" ? (
                    <ShieldCheck className="text-emerald-600" size={18} />
                  ) : testResult.decision.action === "require_approval" ? (
                    <AlertTriangle className="text-amber-600" size={18} />
                  ) : (
                    <Ban className="text-red-600" size={18} />
                  )}
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Simulated Result
                  </p>
                </div>
                <p className="mt-2 text-lg font-bold">
                  {titleCase(testResult.decision.action)}
                </p>
                <p className="mt-1 text-sm font-semibold">
                  {testResult.decision.matched_policy ?? "Semantic risk fallback"}
                </p>
                <p className="mt-2 text-xs leading-relaxed opacity-90">
                  {testResult.decision.reason}
                </p>
              </div>
            ) : null}
            {config ? (
              <div className="rounded-lg border border-dashed border-neutral-300 p-3 text-xs leading-5 text-neutral-600">
                Saved config: {config.config_path}
              </div>
            ) : null}
          </div>
        </Panel>
      </aside>
    </div>
  );
}

export function SlackSurfaceView({
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
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Panel>
        <PanelTitle
          eyebrow="Ambient Surface"
          title="Slack Approval Delivery"
          body="Slack remains the implemented push surface for people who are not watching the ledger."
          icon={<Bell size={18} />}
        />
        <div className="mt-5 grid gap-3 md:grid-cols-[240px_auto]">
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
          <SurfaceStep icon={<ShieldAlert size={16} />} title="Gate Triggered" body="Risky action enters review." />
          <SurfaceStep icon={<Bell size={16} />} title="Slack Posted" body="Human receives concise context." />
          <SurfaceStep icon={<CheckCircle2 size={16} />} title="Ledger Updated" body="Decision becomes replayable." />
        </div>
      </Panel>
      <Panel>
        <PanelTitle eyebrow="Delivery Status" title={result ? "Cards Posted" : "No Cards Sent"} icon={<Network size={18} />} />
        {result ? (
          <div className="mt-5 grid gap-3">
            <Fact label="Session" value={shortId(result.session_id)} />
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

export function AuditEventsView({
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
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] gap-6">
      <Panel>
        <PanelTitle
          eyebrow="Audit Events"
          title="Session Replay"
          icon={<FileText size={18} />}
        />
        <div className="mt-4">
          <p className="text-sm text-neutral-500 mb-4">
            Every trace, policy decision, and human action is rendered as an audit record.
          </p>
          {traces.length === 0 && gates.length === 0 ? (
            <EmptyState
              title="No audit events yet"
              body="Start a Codex session to populate the ledger."
            />
          ) : (
            <div className="grid gap-3">
              {traces.map((trace, index) => (
                <LedgerRow
                  key={trace.id}
                  label={`Trace ${index + 1}`}
                  title={toolLabel(trace.tool_name)}
                  body={trace.stated_reason ?? summarizeTrace(trace)}
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
          )}
        </div>
      </Panel>

      <Panel>
        <PanelTitle
          eyebrow="Analytics"
          title="Ledger Analytics"
          icon={<BarChart3 size={18} />}
        />
        <div className="mt-4">
          <AnalyticsContent analytics={analytics} trustScore={trustScore} />
        </div>
      </Panel>
    </div>
  );
}

export function MetricsStrip({ gates, traces, analytics, trustScore, sessionId }: { gates: Gate[]; traces: TraceEvent[]; analytics: LedgerAnalytics | null; trustScore: number | null; sessionId: string | null }) {
  const pending = gates.filter((gate) => gate.status === "pending").length;
  const resolved = gates.filter((gate) => gate.status !== "pending").length;
  const critical = gates.filter((gate) => ["critical", "high"].includes(gate.risk_assessment.risk_level)).length;
  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
      <Metric label="Session" value={sessionId ? shortId(sessionId) : "Idle"} icon={<Terminal size={16} />} />
      <Metric label="Actions" value={String(traces.length)} icon={<Blocks size={16} />} />
      <Metric label="Pending" value={String(pending)} accent="sky" icon={<AlertTriangle size={16} />} />
      <Metric label="Resolved" value={String(resolved)} accent="green" icon={<CheckCircle2 size={16} />} />
      <Metric label="High Risk" value={String(critical)} accent={critical ? "red" : "neutral"} icon={<ShieldAlert size={16} />} />
      <Metric label="Trust" value={trustScore === null ? "--" : `${trustScore}%`} icon={<BarChart3 size={16} />} sublabel={analytics ? `${analytics.trust_score.total_actions} actions` : undefined} />
    </section>
  );
}

function TimelineLedger({ traces, gates, compact = false }: { traces: TraceEvent[]; gates: Gate[]; compact?: boolean }) {
  const inspectionTraces = traces.filter((trace) => isInspectionTrace(trace));
  const visibleTraces = traces.filter((trace) => !isInspectionTrace(trace));
  return (
    <Panel>
      <PanelTitle eyebrow="Trace Capture" title="Execution Timeline" icon={<Terminal size={18} />} small={compact} />
      <div className="mt-4 flex flex-col gap-3">
        {traces.length === 0 ? <p className="text-sm text-neutral-500">No intercepted tool calls yet.</p> : null}
        {inspectionTraces.length > 0 ? (
          <div className="border-l-2 border-emerald-300 pl-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Inspection Batch</p>
            <p className="mt-1 text-sm leading-6 text-neutral-700">
              {inspectionTraces.length} read-only commands captured and auto-executed.
            </p>
          </div>
        ) : null}
        {visibleTraces.map((trace, index) => (
          <div key={trace.id} className="border-l-2 border-neutral-300 pl-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Step {index + 1} / {toolLabel(trace.tool_name)}
            </p>
            <p className="mt-1 text-sm leading-6 text-neutral-700">{trace.stated_reason || summarizeTrace(trace)}</p>
          </div>
        ))}
        {gates.filter((gate) => gate.status !== "auto_executed").slice(-4).map((gate) => (
          <div key={gate.id} className="border-l-2 border-sky-300 pl-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{titleCase(gate.status)} Gate</p>
            <p className="mt-1 text-sm leading-6 text-neutral-700">{gate.intelligence_card?.summary ?? gate.policy_decision.reason}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function TrajectoryCard({ gate, trace, step }: { gate: Gate; trace: TraceEvent | undefined; step: number }) {
  return (
    <div className="grid gap-4 rounded-lg border border-neutral-200 bg-white p-4 md:grid-cols-[42px_minmax(0,1fr)_140px]">
      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-neutral-950 text-sm font-semibold text-white">{step}</div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <RiskBadge risk={gate.risk_assessment.risk_level} />
          <StatusBadge status={gate.status} />
        </div>
        <h3 className="mt-3 truncate text-base font-semibold">
          {toolLabel(trace?.tool_name)} on {gateTarget(gate, trace)}
        </h3>
        <p className="mt-2 text-sm leading-6 text-neutral-600">
          {gate.intelligence_card?.trajectory_preview ?? "No trajectory preview available."}
        </p>
      </div>
      <div className="border-t border-neutral-200 pt-3 md:border-l md:border-t-0 md:pl-4 md:pt-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Confidence</p>
        <p className="mt-1 text-2xl font-semibold">{formatPercent(gate.intelligence_card?.confidence)}</p>
      </div>
    </div>
  );
}

function EmptyQueue({ sessionId, apiUrl, localGuardMode }: { sessionId: string | null; apiUrl: string; localGuardMode: boolean }) {
  const title = sessionId ? "Live Session is Listening" : "Waiting for Codex Activity";
  const body = sessionId
    ? localGuardMode
      ? "Continue working in Codex. AgentLens will capture tool proposals into this ledger in real-time."
      : "Run the local adapter to forward Codex events into this hosted review queue."
    : "Start a Codex session through the local guard, terminal runner, or native proxy.";

  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-neutral-300 bg-white py-12 px-6 text-center shadow-sm">
      <div className="relative mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-neutral-50 border border-neutral-200">
        <Terminal className="text-neutral-500" size={24} />
        {sessionId ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75 animate-pulse"></span>
            <span className="relative inline-flex h-3.5 w-3.5 rounded-full bg-emerald-500 border-2 border-white"></span>
          </span>
        ) : (
          <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5">
            <span className="relative inline-flex h-3.5 w-3.5 rounded-full bg-amber-500 border-2 border-white"></span>
          </span>
        )}
      </div>
      <h3 className="text-lg font-semibold text-neutral-900 tracking-tight">{title}</h3>
      <p className="mt-2 max-w-md text-sm text-neutral-600 leading-relaxed">{body}</p>

      {!localGuardMode && sessionId ? (
        <div className="mt-6 w-full max-w-xl text-left">
          <div className="flex items-center justify-between rounded-t-lg bg-neutral-900 px-4 py-2 border-b border-neutral-800">
            <div className="flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500"></span>
              <span className="h-2.5 w-2.5 rounded-full bg-yellow-500"></span>
              <span className="h-2.5 w-2.5 rounded-full bg-green-500"></span>
            </div>
            <span className="text-[10px] font-mono text-neutral-400">bash</span>
          </div>
          <code className="block overflow-x-auto rounded-b-lg bg-neutral-950 p-4 font-mono text-xs leading-relaxed text-emerald-400 border border-t-0 border-neutral-800 shadow-inner">
            cd backend && uv run agentlens-codex --api-url {apiUrl} --repo /path/to/your/repo &quot;Inspect this repo&quot;
          </code>
        </div>
      ) : null}
    </div>
  );
}

function answerExplainQuestion(question: string, explain: ExplainMoreResponse) {
  const lower = question.toLowerCase();
  if (lower.includes("risk") || lower.includes("danger")) {
    return explain.risk.evidence[0] ?? explain.context_summary;
  }
  if (lower.includes("policy")) {
    return `${explain.policy.matched_policy ?? "Semantic risk"} produced ${titleCase(explain.policy.action)} because ${explain.policy.reason}.`;
  }
  if (lower.includes("confidence")) {
    return explain.confidence_evidence[0]?.detail ?? "No confidence factor was recorded for this gate.";
  }
  if (lower.includes("depend") || lower.includes("reference")) {
    return explain.dependency_evidence[0]?.summary ?? "No dependency references were recorded for this gate.";
  }
  if (lower.includes("next") || lower.includes("trajectory")) {
    return explain.trajectory?.next_steps[0]?.rationale ?? explain.trajectory?.rationale ?? "No trajectory was recorded.";
  }
  return explain.context_summary;
}

function SectionHeader({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="border-b border-neutral-200 pb-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">{eyebrow}</p>
      <h2 className="mt-1 text-2xl font-bold leading-tight text-neutral-900">{title}</h2>
      {body ? (
        <p className="mt-2 max-w-4xl text-sm leading-relaxed text-neutral-600">
          {body}
        </p>
      ) : null}
    </div>
  );
}

export function TimelineAnalyticsTabs({
  traces,
  gates,
  analytics,
  trustScore,
}: {
  traces: TraceEvent[];
  gates: Gate[];
  analytics: LedgerAnalytics | null;
  trustScore: number | null;
}) {
  const [activeTab, setActiveTab] = useState<"timeline" | "analytics">("timeline");

  return (
    <section className="rounded-lg border border-neutral-200 bg-white shadow-sm overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-neutral-200 px-5 bg-neutral-50/50">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab("timeline")}
            className={`flex items-center gap-2 border-b-2 py-4 text-xs font-bold uppercase tracking-wider transition outline-none ${
              activeTab === "timeline"
                ? "border-neutral-900 text-neutral-900"
                : "border-transparent text-neutral-400 hover:text-neutral-700"
            }`}
          >
            <Terminal size={14} />
            Execution Timeline
            <span className="inline-flex items-center justify-center rounded-full bg-neutral-200 text-neutral-800 text-[10px] font-bold px-1.5 py-0.5 leading-none">
              {traces.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("analytics")}
            className={`flex items-center gap-2 border-b-2 py-4 text-xs font-bold uppercase tracking-wider transition outline-none ${
              activeTab === "analytics"
                ? "border-neutral-900 text-neutral-900"
                : "border-transparent text-neutral-400 hover:text-neutral-700"
            }`}
          >
            <BarChart3 size={14} />
            Ledger Analytics
            {trustScore !== null && (
              <span className="inline-flex items-center justify-center rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold px-1.5 py-0.5 leading-none">
                {trustScore}%
              </span>
            )}
          </button>
        </div>
        <div className="py-2.5 sm:py-0 text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
          Audit Intelligence Console
        </div>
      </div>

      <div className="p-6">
        {activeTab === "timeline" ? (
          <TimelineContent traces={traces} gates={gates} />
        ) : (
          <AnalyticsContent analytics={analytics} trustScore={trustScore} />
        )}
      </div>
    </section>
  );
}

function TimelineContent({ traces, gates }: { traces: TraceEvent[]; gates: Gate[] }) {
  const inspectionTraces = traces.filter((trace) => isInspectionTrace(trace));
  const visibleTraces = traces.filter((trace) => !isInspectionTrace(trace));

  if (traces.length === 0) {
    return (
      <EmptyState
        title="No intercepted tool calls yet"
        body="Continue working in Codex. AgentLens will automatically stream the execution timeline."
      />
    );
  }

  return (
    <div className="relative border-l-2 border-neutral-200 pl-6 ml-3 space-y-6 py-1">
      {inspectionTraces.length > 0 ? (
        <div className="relative">
          <span className="absolute -left-[31px] top-1 flex h-4 w-4 items-center justify-center rounded-full border border-emerald-400 bg-white">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          </span>
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">Inspection Batch</p>
          <p className="mt-1 text-sm font-semibold text-neutral-900">Captured and auto-executed</p>
          <p className="mt-1 text-xs text-neutral-500 leading-relaxed">
            {inspectionTraces.length} read-only commands and file queries collapsed.
          </p>
        </div>
      ) : null}

      {visibleTraces.map((trace, index) => (
        <div key={trace.id} className="relative">
          <span className="absolute -left-[31px] top-1 flex h-4 w-4 items-center justify-center rounded-full border border-neutral-400 bg-white">
            <span className="h-1.5 w-1.5 rounded-full bg-neutral-600" />
          </span>
          <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
            Step {index + 1} &bull; {toolLabel(trace.tool_name)}
          </p>
          <p className="mt-1 text-sm font-medium text-neutral-800">
            {trace.stated_reason || summarizeTrace(trace)}
          </p>
        </div>
      ))}

      {gates.filter((gate) => gate.status !== "auto_executed").slice(-4).map((gate) => (
        <div key={gate.id} className="relative">
          <span className="absolute -left-[31px] top-1 flex h-4 w-4 items-center justify-center rounded-full border border-sky-400 bg-white">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-pulse" />
          </span>
          <p className="text-xs font-semibold uppercase tracking-wider text-sky-700">
            {titleCase(gate.status)} Gate
          </p>
          <p className="mt-1 text-sm text-neutral-700">
            {gate.intelligence_card?.summary ?? gate.policy_decision.reason}
          </p>
        </div>
      ))}
    </div>
  );
}

function AnalyticsContent({
  analytics,
  trustScore,
}: {
  analytics: LedgerAnalytics | null;
  trustScore: number | null;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-5 md:grid-cols-2">
        <ChartBlock title="Approval Patterns">
          <BucketBarChart buckets={analytics?.approval_patterns ?? []} />
        </ChartBlock>
        <ChartBlock title="Risk Distribution">
          <BucketBarChart buckets={analytics?.risk_distribution ?? []} />
        </ChartBlock>
      </div>

      <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Trust Score Basis</p>
          <p className="mt-1.5 text-sm text-neutral-700 leading-relaxed">
            {analytics
              ? `${analytics.trust_score.auto_executed} actions auto-executed, ${analytics.trust_score.human_interventions} required human intervention.`
              : "No actions recorded yet."}
          </p>
        </div>
        {trustScore !== null && (
          <div className="shrink-0 flex items-center gap-3 border-t md:border-t-0 md:border-l border-neutral-200 pt-3 md:pt-0 md:pl-6">
            <div className="text-right">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-neutral-400 block">Trust Level</span>
              <span className="text-2xl font-bold text-neutral-900">{trustScore}%</span>
            </div>
            <div className="h-10 w-10 flex items-center justify-center rounded-full bg-emerald-50 text-emerald-600 border border-emerald-100">
              <ShieldCheck size={20} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Panel({ children }: { children: ReactNode }) {
  return <section className="min-w-0 rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">{children}</section>;
}

function PanelTitle({
  eyebrow,
  title,
  body,
  icon,
  small = false,
}: {
  eyebrow: string;
  title: string;
  body?: string;
  icon?: ReactNode;
  small?: boolean;
}) {
  return (
    <div>
      <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {icon}
        {eyebrow}
      </p>
      <h2 className={`mt-1 font-semibold leading-tight ${small ? "text-lg" : "text-xl"}`}>{title}</h2>
      {body ? <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-600">{body}</p> : null}
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

function Fact({ label, value }: { label: string; value: string }) {
  const colors: Record<string, string> = {
    Low: "text-emerald-600 bg-emerald-50 border-emerald-100",
    Medium: "text-amber-600 bg-amber-50 border-amber-100",
    High: "text-orange-600 bg-orange-50 border-orange-100",
    Critical: "text-red-600 bg-red-50 border-red-100",
  };

  const badgeColor = colors[value] ?? "text-neutral-800 bg-neutral-50 border-neutral-200";

  return (
    <div className={`border rounded-lg p-3 text-center transition hover:bg-white hover:shadow-sm duration-200 ${badgeColor}`}>
      <p className="text-[9px] font-bold uppercase tracking-wider opacity-85">{label}</p>
      <p className="mt-1 truncate text-sm font-bold">{value}</p>
    </div>
  );
}

function ChartBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex h-56 flex-col rounded-md border border-neutral-200 bg-neutral-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{title}</p>
      <div className="mt-2 min-h-0 flex-1">{children}</div>
    </div>
  );
}

function Metric({
  label,
  value,
  sublabel,
  accent = "neutral",
  icon,
}: {
  label: string;
  value: string;
  sublabel?: string;
  accent?: "neutral" | "green" | "sky" | "red";
  icon: ReactNode;
}) {
  const borderStyles = {
    neutral: "border-neutral-200",
    green: "border-emerald-200",
    sky: "border-sky-200",
    red: "border-red-200",
  };
  
  const iconColor = {
    neutral: "text-neutral-400",
    green: "text-emerald-500",
    sky: "text-sky-500",
    red: "text-red-500",
  };

  const bgStyles = {
    neutral: "bg-white",
    green: "bg-white",
    sky: "bg-white",
    red: "bg-white",
  };

  return (
    <div className={`rounded-lg border ${borderStyles[accent]} ${bgStyles[accent]} p-4 shadow-sm`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-bold uppercase tracking-wider text-neutral-500">{label}</p>
        <span className={iconColor[accent]}>{icon}</span>
      </div>
      <p className="mt-2.5 truncate text-2xl font-bold tracking-tight text-neutral-900 leading-none">{value}</p>
      {sublabel ? <p className="mt-1 text-[11px] font-medium text-neutral-400">{sublabel}</p> : null}
    </div>
  );
}

export function Notice({ tone, children }: { tone: "blue" | "red"; children: ReactNode }) {
  const styles = {
    blue: "border-sky-200 bg-sky-50 text-sky-900",
    red: "border-red-200 bg-red-50 text-red-800",
  };
  return <div className={`rounded-lg border px-4 py-3 text-sm ${styles[tone]}`}>{children}</div>;
}

function RiskCell({ risk }: { risk: RiskLevel }) {
  return (
    <span className="flex items-center gap-2 text-sm font-semibold">
      <span className={`h-2.5 w-2.5 rounded-full ${riskDot[risk]}`} />
      {titleCase(risk)}
    </span>
  );
}

function RiskBadge({ risk }: { risk: RiskLevel }) {
  return <span className={`w-fit rounded-full border px-2.5 py-1 text-xs font-semibold ${riskChip[risk]}`}>{titleCase(risk)}</span>;
}

function StatusBadge({ status }: { status: GateStatus }) {
  const icon =
    status === "blocked" ? <XCircle size={13} />
    : status === "pending" ? <AlertTriangle size={13} />
    : <CheckCircle2 size={13} />;
  return (
    <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${statusChip[status]}`}>
      {icon}
      {titleCase(status)}
    </span>
  );
}

function DecisionButton({
  tone,
  onClick,
  children,
}: {
  tone: "approve" | "block" | "modify";
  onClick: () => void;
  children: ReactNode;
}) {
  const styles = {
    approve: "bg-emerald-600 text-white hover:bg-emerald-700 border-transparent shadow-sm",
    block: "bg-red-50 border border-red-200 text-red-700 hover:bg-red-100",
    modify: "bg-white border border-neutral-300 text-neutral-700 hover:border-neutral-900 hover:text-neutral-900",
  };

  const icons = {
    approve: <Check size={14} className="mr-1.5 shrink-0" />,
    block: <Ban size={14} className="mr-1.5 shrink-0" />,
    modify: <Edit3 size={14} className="mr-1.5 shrink-0" />,
  };

  return (
    <button
      onClick={onClick}
      className={`h-10 flex items-center justify-center rounded-md text-xs font-bold uppercase tracking-wider transition ${styles[tone]}`}
    >
      {icons[tone]}
      {children}
    </button>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-neutral-300 bg-neutral-50/50 py-10 px-4 text-center">
      <Info className="text-neutral-400 mb-3" size={24} />
      <p className="font-semibold text-neutral-900">{title}</p>
      <p className="mt-1.5 max-w-xs text-xs leading-relaxed text-neutral-500">{body}</p>
    </div>
  );
}

function SurfaceStep({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4">
      <p className="flex h-8 w-8 items-center justify-center rounded-md bg-neutral-950 text-white">{icon}</p>
      <p className="mt-3 text-sm font-semibold">{title}</p>
      <p className="mt-1 text-sm leading-5 text-neutral-600">{body}</p>
    </div>
  );
}

function LedgerRow({ label, title, body }: { label: string; title: string; body: string }) {
  return (
    <div className="grid gap-3 rounded-lg border border-neutral-200 bg-white p-4 md:grid-cols-[140px_minmax(0,1fr)]">
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</p>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{title}</p>
        <p className="mt-1 line-clamp-2 text-sm leading-6 text-neutral-600">{body}</p>
      </div>
    </div>
  );
}

function StatusLine({ label, value, ok, collapsed = false }: { label: string; value: string; ok: boolean; collapsed?: boolean }) {
  if (collapsed) {
    return (
      <div className="flex items-center justify-center py-1.5" title={`${label}: ${value}`}>
        <span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-400" : "bg-amber-400"}`} />
      </div>
    );
  }
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
