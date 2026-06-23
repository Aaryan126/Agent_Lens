"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  type Node,
  type Edge,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import {
  AlertTriangle,
  Ban,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Edit3,
  GitBranch,
  Grid,
  Lock,
  Maximize2,
  Play,
  ShieldAlert,
  Sparkles,
  Terminal,
  Unlock,
  XCircle,
} from "lucide-react";

import type { Gate, GateStatus, RiskLevel, SessionSummary, TraceEvent, ExplainMoreResponse, ReviewEpisode } from "../types";
import {
  formatPercent,
  gateTarget,
  episodePrimaryGate,
  statusChip,
  titleCase,
  toolLabel,
} from "../utils";
import { GateInspector } from "./ledger-ui";

const NODE_WIDTH = 280;
const NODE_HEIGHT = 124;
const GAP_X = 130;
const GAP_Y = 190;
const ROW_CAPACITY = 3;

const riskBorder: Record<RiskLevel, string> = {
  low: "border-emerald-300",
  medium: "border-amber-300",
  high: "border-orange-300",
  critical: "border-red-300",
};

const statusIcon: Record<GateStatus, React.ReactNode> = {
  pending: <AlertTriangle size={12} />,
  approved: <Check size={12} />,
  blocked: <Ban size={12} />,
  modified: <Edit3 size={12} />,
  auto_executed: <CheckCircle2 size={12} />,
};

type FlowMapViewProps = {
  session: SessionSummary | null;
  gates: Gate[];
  traces: TraceEvent[];
  episodes: ReviewEpisode[];
  traceByProposal: Map<string, TraceEvent>;
  apiUrl: string;
  localGuardMode: boolean;
  decisionNote: string;
  explain: ExplainMoreResponse | null;
  explainLoading: boolean;
  explainError: string | null;
  onDecisionNote: (value: string) => void;
  onDecision: (gate: Gate, action: "approve" | "block" | "modify") => Promise<void>;
  onExplain: (gate: Gate) => Promise<void>;
  onSelectGate: (gateId: string) => void;
};

export function FlowMapView(props: FlowMapViewProps) {
  return (
    <ReactFlowProvider>
      <FlowMapInner {...props} />
    </ReactFlowProvider>
  );
}

type TaskGroup = {
  prompt: string;
  items: ReviewEpisode[];
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
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
    <div className={`border rounded-lg p-2.5 text-center transition hover:bg-white hover:shadow-sm duration-200 ${badgeColor}`}>
      <p className="text-[9px] font-bold uppercase tracking-wider opacity-85">{label}</p>
      <p className="mt-1 truncate text-sm font-bold">{value}</p>
    </div>
  );
}

function GitDiffViewer({ diff }: { diff: string }) {
  if (!diff || !diff.trim()) {
    return <p className="text-xs text-neutral-500 italic">No code changes recorded in this snapshot.</p>;
  }

  const lines = diff.split("\n");
  return (
    <pre className="text-xs font-mono bg-neutral-950 p-4 rounded-md overflow-x-auto max-h-[300px] leading-relaxed">
      {lines.map((line, idx) => {
        let color = "text-neutral-300";
        if (line.startsWith("+") && !line.startsWith("+++")) {
          color = "text-emerald-400 bg-emerald-950/40 px-1";
        } else if (line.startsWith("-") && !line.startsWith("---")) {
          color = "text-rose-400 bg-rose-950/40 px-1";
        } else if (line.startsWith("@@")) {
          color = "text-blue-400 font-bold";
        } else if (line.startsWith("diff") || line.startsWith("index")) {
          color = "text-neutral-500";
        }
        return (
          <div key={idx} className={color}>
            {line}
          </div>
        );
      })}
    </pre>
  );
}

function TraceInspector({
  trace,
  onClose,
}: {
  trace: TraceEvent;
  onClose: () => void;
}) {
  return (
    <aside className="sticky top-5 flex max-h-[calc(100vh-1.5rem)] flex-col overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-neutral-200 p-5 pb-4 bg-neutral-50/50">
        <div className="min-w-0">
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 border border-emerald-100 rounded px-1.5 py-0.5">Observed Trace</span>
          <h3 className="mt-2 text-base font-bold text-neutral-900 leading-tight">
            {toolLabel(trace.tool_name)}
          </h3>
          <p className="mt-2 text-xs text-neutral-500 leading-relaxed break-all font-semibold">
            {String(trace.params.path ?? trace.params.command ?? trace.params.cmd ?? "Tool call")}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-neutral-400 hover:text-neutral-600 transition p-1"
          title="Close Inspector"
        >
          <XCircle size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {trace.stated_reason ? (
          <Section title="Stated Reason">
            <p className="text-sm text-neutral-700 leading-relaxed italic bg-neutral-50 border border-neutral-100 rounded-md p-3">
              "{trace.stated_reason}"
            </p>
          </Section>
        ) : null}

        {trace.params.cwd ? (
          <Section title="CWD (Working Directory)">
            <code className="text-xs font-mono bg-neutral-50 text-neutral-600 border border-neutral-100 rounded p-1.5 block truncate">
              {String(trace.params.cwd)}
            </code>
          </Section>
        ) : null}

        {trace.git_snapshot?.status_short ? (
          <Section title="Git Snapshot Status">
            <pre className="text-xs font-mono bg-neutral-50 text-neutral-600 border border-neutral-100 rounded-md p-3 whitespace-pre-wrap">
              {trace.git_snapshot.status_short}
            </pre>
          </Section>
        ) : null}

        {trace.git_snapshot?.diff ? (
          <Section title="Git Diff Excerpt">
            <GitDiffViewer diff={trace.git_snapshot.diff} />
          </Section>
        ) : null}

        <Section title="Action Parameters">
          <pre className="text-xs font-mono bg-neutral-950 text-emerald-400 rounded-md p-4 overflow-x-auto max-h-[220px]">
            {JSON.stringify(trace.params, null, 2)}
          </pre>
        </Section>
      </div>
    </aside>
  );
}

function StartNodeInspector({
  label,
  instruction,
  onClose,
}: {
  label: string;
  instruction: string;
  onClose: () => void;
}) {
  return (
    <aside className="sticky top-5 flex max-h-[calc(100vh-1.5rem)] flex-col overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-neutral-200 p-5 pb-4 bg-neutral-50/50">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500 bg-neutral-100 border border-neutral-200 rounded px-1.5 py-0.5">Task Segment Trigger</span>
          <h3 className="mt-2 text-base font-bold text-neutral-900 leading-tight">
            {label}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-neutral-400 hover:text-neutral-600 transition p-1"
          title="Close Inspector"
        >
          <XCircle size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        <Section title="User Prompt / Instruction">
          <p className="text-sm text-neutral-700 leading-relaxed font-semibold bg-neutral-50 border border-neutral-100 rounded-md p-3.5">
            {instruction}
          </p>
        </Section>
      </div>
    </aside>
  );
}

function EpisodeInspector({
  episode,
  onClose,
}: {
  episode: ReviewEpisode;
  onClose: () => void;
}) {
  return (
    <aside className="sticky top-5 flex max-h-[calc(100vh-1.5rem)] flex-col overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-neutral-200 p-5 pb-4 bg-neutral-50/50">
        <div className="min-w-0">
          <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500 bg-neutral-100 border border-neutral-200 rounded px-1.5 py-0.5">
            {titleCase(episode.kind)}
          </span>
          <h3 className="mt-2 text-base font-bold text-neutral-900 leading-tight">
            {episode.descriptor.human_title}
          </h3>
          <p className="mt-2 text-xs text-neutral-500 leading-relaxed">
            {episode.trace_ids.length} raw trace(s), {episode.gate_ids.length} gate record(s).
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-neutral-400 hover:text-neutral-600 transition p-1"
          title="Close Inspector"
        >
          <XCircle size={16} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        <Section title="Narrative Summary">
          <p>{episode.summary}</p>
        </Section>
        <Section title="Evidence">
          <p>{episode.descriptor.evidence_summary}</p>
        </Section>
        {episode.descriptor.raw_detail ? (
          <Section title="Raw Detail">
            <code className="block rounded-md border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-700">
              {episode.descriptor.raw_detail}
            </code>
          </Section>
        ) : null}
      </div>
    </aside>
  );
}

function FlowMapInner({
  session,
  gates,
  traces,
  episodes,
  traceByProposal,
  apiUrl,
  localGuardMode,
  decisionNote,
  explain,
  explainLoading,
  explainError,
  onDecisionNote,
  onDecision,
  onExplain,
  onSelectGate,
}: FlowMapViewProps) {
  const { fitView } = useReactFlow();
  const [mounted, setMounted] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const interactive = true;
  const showGrid = true;

  const ordered = useMemo(() => episodes, [episodes]);

  const groups = useMemo(() => {
    const list: TaskGroup[] = [];
    ordered.forEach((item) => {
      const prompt = item.prompt || session?.original_instruction || "Original Task";
      let lastGroup = list[list.length - 1];
      if (!lastGroup || lastGroup.prompt !== prompt) {
        lastGroup = { prompt, items: [] };
        list.push(lastGroup);
      }
      lastGroup.items.push(item);
    });
    return list;
  }, [ordered, session?.original_instruction]);

  const { nodes, edges } = useMemo(() => {
    const nodes: Node<FlowNodeData>[] = [];
    const edges: Edge[] = [];

    let currentRow = 0;

    groups.forEach((group, groupIndex) => {
      const startId = `start_${groupIndex}`;
      const endId = `end_${groupIndex}`;

      // Start node for this task group
      nodes.push({
        id: startId,
        type: "start",
        position: { x: 0, y: currentRow * (NODE_HEIGHT + GAP_Y) + (NODE_HEIGHT / 4) },
        data: {
          instruction: group.prompt,
          label: groupIndex === 0 ? "Original Task" : `Task ${groupIndex + 1}`,
          onSelect: () => setSelectedNodeId(startId),
          isSelected: selectedNodeId === startId,
        },
      });

      let lastId = startId;

      group.items.forEach((item, itemIndex) => {
        const nodeIndexInGroup = itemIndex + 1;
        const col = nodeIndexInGroup % ROW_CAPACITY;
        const rowOffset = Math.floor(nodeIndexInGroup / ROW_CAPACITY);
        const x = col * (NODE_WIDTH + GAP_X);
        const y = (currentRow + rowOffset) * (NODE_HEIGHT + GAP_Y);
        const id = item.id;

        const onSelect = () => setSelectedNodeId(id);
        const isSelected = selectedNodeId === id;

        nodes.push(episodeNode(id, item, gates, { x, y }, onSelectGate, onSelect, isSelected));

        edges.push(flowEdge(lastId, id, episodePrimaryGate(item, gates)));
        lastId = id;
      });

      // End node for this task group
      const endNodeIndex = group.items.length + 1;
      const endCol = endNodeIndex % ROW_CAPACITY;
      const endRowOffset = Math.floor(endNodeIndex / ROW_CAPACITY);
      const endX = endCol * (NODE_WIDTH + GAP_X);
      const endY = (currentRow + endRowOffset) * (NODE_HEIGHT + GAP_Y);

      nodes.push({
        id: endId,
        type: "end",
        position: { x: endX, y: endY },
        data: {},
      });

      edges.push(flowEdge(lastId, endId, null));

      // Calculate total rows in this group
      currentRow += endRowOffset + 1.8;
    });

    return { nodes, edges };
  }, [groups, onSelectGate, selectedNodeId]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const timer = window.setTimeout(() => {
      void fitView({ padding: 0.18, duration: 400 });
    }, 100);
    return () => window.clearTimeout(timer);
  }, [fitView, mounted, nodes.length, edges.length]);

  const handleZoomToFit = () => {
    void fitView({ padding: 0.18, duration: 300 });
  };

  const renderInspector = () => {
    if (!selectedNodeId) {
      return (
        <aside className="flex flex-col justify-between rounded-xl border border-neutral-200 bg-white p-6 shadow-sm min-h-[400px]">
          <div className="flex flex-col items-center justify-center flex-1 py-8 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-neutral-50 border border-neutral-200 text-neutral-400">
              <Sparkles size={22} />
            </div>
            <h3 className="text-base font-bold text-neutral-900 tracking-tight">Active Inspector</h3>
            <p className="mt-2 max-w-xs text-xs text-neutral-500 leading-relaxed">
              Select any node from the flow map on the left to analyze its code diff, stated rationale, trajectory prediction, and policy decisions.
            </p>
          </div>
          <div className="border-t border-neutral-100 pt-5 space-y-2.5">
            <div className="flex items-center justify-between text-xs py-1.5 border-b border-neutral-50">
              <span className="font-semibold text-neutral-400 uppercase tracking-wider">Map Mode</span>
              <span className="font-bold text-neutral-800">Task Grouped</span>
            </div>
            <div className="flex items-center justify-between text-xs py-1.5 border-b border-neutral-50">
              <span className="font-semibold text-neutral-400 uppercase tracking-wider">Canvas State</span>
              <span className="font-bold text-neutral-800">{interactive ? "Interactive" : "Locked"}</span>
            </div>
            <div className="flex items-center justify-between text-xs py-1.5">
              <span className="font-semibold text-neutral-400 uppercase tracking-wider">Total Groups</span>
              <span className="font-bold text-neutral-800">{groups.length}</span>
            </div>
          </div>
        </aside>
      );
    }

    if (selectedNodeId.startsWith("start_")) {
      const groupIndex = parseInt(selectedNodeId.split("_")[1], 10);
      const group = groups[groupIndex];
      if (group) {
        return (
          <StartNodeInspector
            label={groupIndex === 0 ? "Original Task" : `Task ${groupIndex + 1}`}
            instruction={group.prompt}
            onClose={() => setSelectedNodeId(null)}
          />
        );
      }
    }

    const selectedEpisode = episodes.find((episode) => episode.id === selectedNodeId);
    const selectedGate = selectedEpisode ? episodePrimaryGate(selectedEpisode, gates) : gates.find((g) => g.id === selectedNodeId || g.proposal_id === selectedNodeId);
    if (selectedGate) {
      return (
        <div className="flex flex-col gap-3">
          <button
            onClick={() => onSelectGate(selectedGate.id)}
            className="flex items-center gap-1.5 text-xs font-semibold text-neutral-500 hover:text-neutral-900 transition self-start"
          >
            <ClipboardList size={14} />
            Open in Review Queue
          </button>
          <GateInspector
            gate={selectedGate}
            trace={traceByProposal.get(selectedGate.proposal_id)}
            apiUrl={apiUrl}
            decisionNote={decisionNote}
            explain={explain}
            explainLoading={explainLoading}
            explainError={explainError}
            onDecisionNote={onDecisionNote}
            onDecision={onDecision}
            onExplain={onExplain}
          />
        </div>
      );
    }

    if (selectedEpisode) {
      return <EpisodeInspector episode={selectedEpisode} onClose={() => setSelectedNodeId(null)} />;
    }

    const selectedTrace = traces.find((t) => t.id === selectedNodeId);
    if (selectedTrace) {
      return (
        <TraceInspector
          trace={selectedTrace}
          onClose={() => setSelectedNodeId(null)}
        />
      );
    }

    return null;
  };

  return (
    <section className="grid grid-cols-1 xl:grid-cols-[1fr_480px] gap-5 items-start">
      {/* Flow Map Canvas Column */}
      <div className="flex flex-col rounded-lg border border-neutral-200 bg-white shadow-sm min-w-0">
        <div className="flex flex-col gap-4 border-b border-neutral-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
              <Sparkles size={14} />
              Agent Flow Map
            </p>
            <h2 className="mt-1 text-xl font-semibold leading-tight text-neutral-900">
              Visual supervision of Codex decisions
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-medium text-neutral-500">
              {ordered.length} episode{ordered.length === 1 ? "" : "s"}
            </span>
            <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-neutral-600">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-2.5 py-1">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Low
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-2.5 py-1">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                Med
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-2.5 py-1">
                <span className="h-2 w-2 rounded-full bg-orange-500" />
                High
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-2.5 py-1">
                <span className="h-2 w-2 rounded-full bg-red-500" />
                Crit
              </span>
            </div>
          </div>
        </div>

        {/* Toolbar Controls */}
        <div className="flex items-center justify-between border-b border-neutral-100 bg-neutral-50/50 px-5 py-2">
          <div className="flex items-center gap-2">
            <button
              onClick={handleZoomToFit}
              className="flex items-center gap-1.5 rounded bg-white border border-neutral-200 px-2 py-1 text-xs font-semibold text-neutral-600 hover:border-neutral-950 transition"
              title="Fit View"
            >
              <Maximize2 size={12} />
              Fit View
            </button>
          </div>
          <div className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
            Click nodes to inspect code logs & telemetry
          </div>
        </div>

        <div className="relative h-[720px] w-full">
          {mounted ? (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              fitView
              fitViewOptions={{ padding: 0.18 }}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              nodeTypes={nodeTypes}
              minZoom={0.15}
              maxZoom={2}
              defaultViewport={{ x: 0, y: 0, zoom: 0.85 }}
              proOptions={{ hideAttribution: true }}
              panOnDrag={interactive}
              zoomOnScroll={interactive}
              zoomOnPinch={interactive}
              zoomOnDoubleClick={interactive}
              preventScrolling={interactive}
              onNodeClick={(event, node) => {
                if (node.type === "end") return;
                setSelectedNodeId(node.id);
              }}
            >
              {showGrid ? <Background gap={20} size={1} color="#d4d4d4" /> : null}
              <Controls showInteractive={false} />
            </ReactFlow>
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="rounded-xl border border-dashed border-neutral-300 bg-white px-8 py-6 text-center shadow-sm">
                <Sparkles className="mx-auto mb-3 text-neutral-400" size={28} />
                <p className="font-semibold text-neutral-900">Loading flow map</p>
                <p className="mt-1 text-sm text-neutral-600">Preparing the graph canvas...</p>
              </div>
            </div>
          )}
          {ordered.length === 0 ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-white/60">
              <div className="rounded-xl border border-dashed border-neutral-300 bg-white px-8 py-6 text-center shadow-sm">
                <Terminal className="mx-auto mb-3 text-neutral-400" size={28} />
                <p className="font-semibold text-neutral-900">No agent actions yet</p>
                <p className="mt-1 max-w-xs text-sm text-neutral-600">
                  Start a Codex session to see the tool-call flow appear here.
                </p>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Inspector Details Panel Column */}
      <div className="w-full xl:w-[480px]">
        {renderInspector()}
      </div>
    </section>
  );
}

const nodeTypes = {
  start: StartNode,
  trace: TraceNode,
  gate: GateNode,
  end: EndNode,
};

function StartNode({ data }: { data: FlowNodeData }) {
  const isSelected = data.isSelected;
  return (
    <div
      onClick={data.onSelect}
      className={`relative flex w-[280px] flex-col rounded-xl border-2 text-left p-4 text-white shadow-lg transition hover:bg-neutral-900 cursor-pointer focus:outline-none ${
        isSelected
          ? "border-emerald-500 bg-neutral-950 ring-4 ring-offset-2 ring-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.35)] animate-pulse"
          : "border-neutral-950 bg-neutral-950"
      }`}
    >
      <Handle type="target" position={Position.Left} className="!bg-white" />
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-white/10">
          <Play size={16} className="text-white" />
        </div>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">{data.label || "Original Task"}</p>
      </div>
      <p className="mt-3 line-clamp-4 text-sm font-medium leading-relaxed">{data.instruction || "No instruction set."}</p>
      <Handle type="source" position={Position.Right} className="!bg-white" />
    </div>
  );
}

function EndNode() {
  return (
    <div className="relative flex w-[220px] flex-col items-center justify-center rounded-xl border-2 border-neutral-300 bg-neutral-50 p-4 text-neutral-700 shadow-sm">
      <Handle type="target" position={Position.Left} className="!bg-neutral-400" />
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-neutral-200 text-neutral-700">
        <CheckCircle2 size={20} />
      </div>
      <p className="mt-2 text-sm font-semibold">Task Complete</p>
    </div>
  );
}

function TraceNode({ data }: { data: FlowNodeData }) {
  const isSelected = data.isSelected;
  return (
    <div
      onClick={data.onSelect}
      className={`relative flex w-[280px] flex-col rounded-xl border text-left p-3.5 shadow-sm transition hover:shadow-md cursor-pointer focus:outline-none ${
        isSelected
          ? "border-emerald-500 bg-emerald-50 ring-4 ring-offset-2 ring-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.25)]"
          : "border-emerald-200 bg-emerald-50/70"
      }`}
    >
      <Handle type="target" position={Position.Left} className="!bg-emerald-400" />
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-100 text-emerald-700">
          <Terminal size={14} />
        </div>
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">{data.toolLabel}</p>
      </div>
      <p className="mt-2 line-clamp-3 text-sm font-semibold text-neutral-900">{data.target}</p>
      {data.reason ? (
        <p className="mt-2 line-clamp-2 text-xs leading-5 text-neutral-600">{data.reason}</p>
      ) : null}
      <Handle type="source" position={Position.Right} className="!bg-emerald-400" />
    </div>
  );
}

function GateNode({ data }: { data: FlowNodeData }) {
  const gate = data.gate!;
  const isPending = gate.status === "pending";
  const risk = gate.risk_assessment.risk_level;
  const card = gate.intelligence_card;
  const isSelected = data.isSelected;

  return (
    <div
      onClick={data.onSelect}
      className={`group relative flex w-[280px] flex-col rounded-xl border-2 bg-white p-3.5 text-left shadow-md transition hover:shadow-xl hover:-translate-y-0.5 cursor-pointer focus:outline-none ${
        isSelected
          ? `${riskBorder[risk]} ring-4 ring-offset-2 ${riskRingColor(risk)}`
          : riskBorder[risk]
      } ${isPending ? "animate-pulse" : ""}`}
      style={isPending ? { boxShadow: `0 0 0 4px ${riskShadowColor(risk)}` } : undefined}
    >
      <Handle type="target" position={Position.Left} className="!bg-neutral-400" />
      <div className="flex items-center justify-between gap-2 w-full">
        <div className="flex items-center gap-2 min-w-0">
          <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${iconBg(risk)}`}>
            {risk === "critical" || risk === "high" ? <ShieldAlert size={14} /> : <Bot size={14} />}
          </div>
          <p className="truncate whitespace-nowrap text-[11px] font-bold uppercase tracking-wide text-neutral-500">
            {data.toolLabel} · {formatPercent(card?.confidence ?? 0)} conf
          </p>
        </div>
        <span className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${statusChip[gate.status]}`}>
          {statusIcon[gate.status]}
          {titleCase(gate.status)}
        </span>
      </div>

      <p className="mt-3 line-clamp-2 text-sm font-semibold text-neutral-900">{data.target}</p>

      {card?.summary ? (
        <p className="mt-2 line-clamp-2 text-xs leading-5 text-neutral-600">{card.summary}</p>
      ) : null}

      {card?.drift_flag ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800">
            <GitBranch size={10} />
            Drift
          </span>
        </div>
      ) : null}

      <div className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-neutral-500 opacity-0 transition group-hover:opacity-100">
        Click to inspect
        <ChevronRight size={12} />
      </div>
      <Handle type="source" position={Position.Right} className="!bg-neutral-400" />
    </div>
  );
}

function iconBg(risk: RiskLevel) {
  if (risk === "critical") return "bg-red-100 text-red-700";
  if (risk === "high") return "bg-orange-100 text-orange-700";
  if (risk === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

function riskShadowColor(risk: RiskLevel): string {
  if (risk === "critical") return "rgba(220, 38, 38, 0.35)";
  if (risk === "high") return "rgba(234, 88, 12, 0.35)";
  if (risk === "medium") return "rgba(245, 158, 11, 0.35)";
  return "rgba(16, 185, 129, 0.35)";
}

function riskRingColor(risk: RiskLevel): string {
  if (risk === "critical") return "ring-red-500/20";
  if (risk === "high") return "ring-orange-500/20";
  if (risk === "medium") return "ring-amber-500/20";
  return "ring-emerald-500/20";
}

type FlowItem =
  | { kind: "trace"; trace: TraceEvent }
  | { kind: "gate"; gate: Gate; trace?: TraceEvent };

type FlowNodeData = {
  instruction?: string;
  label?: string;
  toolLabel?: string;
  target?: string;
  reason?: string | null;
  gate?: Gate;
  onSelectGate?: (gateId: string) => void;
  onSelect?: () => void;
  isSelected?: boolean;
};

function buildOrderedItems(gates: Gate[], traces: TraceEvent[], traceByProposal: Map<string, TraceEvent>): FlowItem[] {
  const gateByProposal = new Map<string, Gate>();
  for (const gate of gates) {
    gateByProposal.set(gate.proposal_id, gate);
  }

  const items: FlowItem[] = [];
  const handledProposalIds = new Set<string>();

  for (const trace of traces) {
    const gate = gateByProposal.get(trace.proposal_id);
    if (gate) {
      items.push({ kind: "gate", gate, trace });
      handledProposalIds.add(trace.proposal_id);
    } else {
      items.push({ kind: "trace", trace });
    }
  }

  for (const gate of gates) {
    if (!handledProposalIds.has(gate.proposal_id)) {
      items.push({ kind: "gate", gate, trace: traceByProposal.get(gate.proposal_id) });
    }
  }

  return items.sort((a, b) => {
    const aTime = timestamp(a);
    const bTime = timestamp(b);
    if (aTime && bTime) return aTime - bTime;
    return 0;
  });
}

function timestamp(item: FlowItem): number | null {
  const raw = item.kind === "trace" ? item.trace.created_at : item.gate.created_at;
  if (!raw) return null;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function itemId(item: FlowItem): string {
  return item.kind === "trace" ? item.trace.id : item.gate.id;
}

function traceNode(
  id: string,
  trace: TraceEvent,
  position: { x: number; y: number },
  onSelect: () => void,
  isSelected: boolean,
): Node<FlowNodeData> {
  return {
    id,
    type: "trace",
    position,
    data: {
      toolLabel: toolLabel(trace.tool_name),
      target: String(trace.params.path ?? trace.params.command ?? trace.params.cmd ?? "Tool call"),
      reason: trace.stated_reason,
      onSelect,
      isSelected,
    },
  };
}

function gateNode(
  id: string,
  gate: Gate,
  trace: TraceEvent | undefined,
  position: { x: number; y: number },
  onSelectGate: (gateId: string) => void,
  onSelect: () => void,
  isSelected: boolean,
): Node<FlowNodeData> {
  return {
    id,
    type: "gate",
    position,
    data: {
      gate,
      toolLabel: toolLabel(trace?.tool_name),
      target: gateTarget(gate, trace),
      onSelectGate,
      onSelect,
      isSelected,
    },
  };
}

function episodeNode(
  id: string,
  episode: ReviewEpisode,
  gates: Gate[],
  position: { x: number; y: number },
  onSelectGate: (gateId: string) => void,
  onSelect: () => void,
  isSelected: boolean,
): Node<FlowNodeData> {
  const gate = episodePrimaryGate(episode, gates);
  if (gate) {
    return {
      id,
      type: "gate",
      position,
      data: {
        gate,
        toolLabel: titleCase(episode.kind),
        target: episode.descriptor.human_title,
        onSelectGate,
        onSelect,
        isSelected,
      },
    };
  }
  return {
    id,
    type: "trace",
    position,
    data: {
      toolLabel: titleCase(episode.kind),
      target: episode.descriptor.human_title,
      reason: episode.summary,
      onSelect,
      isSelected,
    },
  };
}

function flowEdge(source: string, target: string, gate: Gate | null): Edge {
  const isPending = gate?.status === "pending";
  return {
    id: `${source}->${target}`,
    source,
    target,
    type: "smoothstep",
    animated: isPending,
    style: { stroke: edgeColor(gate), strokeWidth: isPending ? 3 : 2 },
  };
}

function edgeColor(gate: Gate | null): string {
  if (!gate) return "#10b981";
  const risk = gate.risk_assessment.risk_level;
  if (risk === "critical") return "#dc2626";
  if (risk === "high") return "#ea580c";
  if (risk === "medium") return "#f59e0b";
  return "#10b981";
}
