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
  Edit3,
  GitBranch,
  Play,
  ShieldAlert,
  Sparkles,
  Terminal,
  XCircle,
} from "lucide-react";

import type { Gate, GateStatus, RiskLevel, SessionSummary, TraceEvent } from "../types";
import {
  formatPercent,
  gateTarget,
  statusChip,
  titleCase,
  toolLabel,
} from "../utils";

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
  traceByProposal: Map<string, TraceEvent>;
  onSelectGate: (gateId: string) => void;
};

export function FlowMapView(props: FlowMapViewProps) {
  return (
    <ReactFlowProvider>
      <FlowMapInner {...props} />
    </ReactFlowProvider>
  );
}

function FlowMapInner({ session, gates, traces, traceByProposal, onSelectGate }: FlowMapViewProps) {
  const { fitView } = useReactFlow();
  const [mounted, setMounted] = useState(false);
  const ordered = useMemo(() => buildOrderedItems(gates, traces, traceByProposal), [gates, traces, traceByProposal]);

  const { nodes, edges } = useMemo(() => {
    const nodes: Node<FlowNodeData>[] = [];
    const edges: Edge[] = [];

    nodes.push(startNode(session));

    ordered.forEach((item, index) => {
      const previousId = index === 0 ? "start" : itemId(ordered[index - 1]);
      const id = itemId(item);
      const position = gridPosition(index + 1);

      if (item.kind === "trace") {
        nodes.push(traceNode(id, item.trace, position));
      } else {
        nodes.push(gateNode(id, item.gate, item.trace, position, onSelectGate));

      }
      edges.push(flowEdge(previousId, id, item.kind === "gate" ? item.gate : null));
    });

    if (ordered.length > 0) {
      const lastId = itemId(ordered[ordered.length - 1]);
      const endPosition = gridPosition(ordered.length + 1);
      nodes.push(endNode(endPosition));
      edges.push(flowEdge(lastId, "end", null));
    }

    return { nodes, edges };
  }, [ordered, session, onSelectGate]);

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

  return (
    <section className="flex flex-col rounded-lg border border-neutral-200 bg-white shadow-sm">
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
            {ordered.length} action{ordered.length === 1 ? "" : "s"}
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
          >
            <Background gap={20} size={1} color="#d4d4d4" />
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
  return (
    <div className="relative flex w-[280px] flex-col rounded-xl border-2 border-neutral-950 bg-neutral-950 p-4 text-white shadow-lg">
      <Handle type="target" position={Position.Left} className="!bg-white" />
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-white/10">
          <Play size={16} className="text-white" />
        </div>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-400">Original Task</p>
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
  return (
    <div className="relative flex w-[280px] flex-col rounded-xl border border-emerald-200 bg-emerald-50/70 p-3.5 shadow-sm">
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

  return (
    <button
      onClick={() => data.onSelectGate?.(gate.id)}
      className={`group relative flex w-[280px] flex-col rounded-xl border-2 bg-white p-3.5 text-left shadow-md transition hover:shadow-xl hover:-translate-y-1 focus:outline-none ${
        riskBorder[risk]
      } ${isPending ? "animate-pulse" : ""}`}
      style={isPending ? { boxShadow: `0 0 0 4px ${riskShadowColor(risk)}` } : undefined}
    >
      <Handle type="target" position={Position.Left} className="!bg-neutral-400" />
      <div className="flex items-center justify-between gap-2">
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
    </button>
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

type FlowItem =
  | { kind: "trace"; trace: TraceEvent }
  | { kind: "gate"; gate: Gate; trace?: TraceEvent };

type FlowNodeData = {
  instruction?: string;
  toolLabel?: string;
  target?: string;
  reason?: string | null;
  gate?: Gate;
  onSelectGate?: (gateId: string) => void;
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

function gridPosition(index: number): { x: number; y: number } {
  const row = Math.floor(index / ROW_CAPACITY);
  const col = index % ROW_CAPACITY;
  const x = col * (NODE_WIDTH + GAP_X);
  const y = row * (NODE_HEIGHT + GAP_Y);
  return { x, y };
}

function startNode(session: SessionSummary | null): Node<FlowNodeData> {
  return {
    id: "start",
    type: "start",
    position: { x: 0, y: NODE_HEIGHT / 2 },
    data: { instruction: session?.original_instruction },
  };
}

function endNode(position: { x: number; y: number }): Node<FlowNodeData> {
  return {
    id: "end",
    type: "end",
    position,
    data: {},
  };
}

function traceNode(id: string, trace: TraceEvent, position: { x: number; y: number }): Node<FlowNodeData> {
  return {
    id,
    type: "trace",
    position,
    data: {
      toolLabel: toolLabel(trace.tool_name),
      target: String(trace.params.path ?? trace.params.command ?? trace.params.cmd ?? "Tool call"),
      reason: trace.stated_reason,
    },
  };
}

function gateNode(
  id: string,
  gate: Gate,
  trace: TraceEvent | undefined,
  position: { x: number; y: number },
  onSelectGate: (gateId: string) => void,
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
