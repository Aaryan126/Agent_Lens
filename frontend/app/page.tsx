"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { FlowMapView } from "./components/flow-map-view";
import {
  AppShell,
  AuditEventsView,
  MetricsStrip,
  Notice,
  PolicyLedgerView,
  ReviewLedger,
  SlackSurfaceView,
  TrajectoryView,
} from "./components/ledger-ui";
import type {
  DemoResponse,
  ExplainMoreResponse,
  Gate,
  HealthState,
  LedgerAnalytics,
  SessionSummary,
  SlackSendResult,
  TimelineResponse,
  TraceEvent,
  View,
} from "./types";
import { analyticsWithGateFallback, isInspectionGate, isLocalApi } from "./utils";

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_AGENTLENS_API_URL ?? "http://127.0.0.1:8000";
const DEFAULT_SLACK_CHANNEL = "C0BBW328TEF";
const ACTIVE_SESSION_STORAGE_KEY = "agentlens-active-session-id";
const ACTIVE_API_STORAGE_KEY = "agentlens-api-url";

export default function Home() {
  const [activeView, setActiveView] = useState<View>("review");
  const [demo, setDemo] = useState<DemoResponse | null>(null);
  const [analytics, setAnalytics] = useState<LedgerAnalytics | null>(null);
  const [selectedGateId, setSelectedGateId] = useState<string | null>(null);
  const [slackLoading, setSlackLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthState>("checking");
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [pinnedSessionId, setPinnedSessionId] = useState<string | null>(null);
  const [recentSessions, setRecentSessions] = useState<SessionSummary[]>([]);
  const [slackChannel, setSlackChannel] = useState(DEFAULT_SLACK_CHANNEL);
  const [decisionNote, setDecisionNote] = useState("Reviewed in AgentLens ledger.");
  const [slackResult, setSlackResult] = useState<SlackSendResult | null>(null);
  const [explain, setExplain] = useState<ExplainMoreResponse | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);

  const gates = demo?.timeline.gates ?? [];
  const traces = demo?.timeline.traces ?? [];
  const traceByProposal = useMemo(
    () => new Map(traces.map((trace) => [trace.proposal_id, trace])),
    [traces],
  );
  const selectedGate =
    gates.find((gate) => gate.id === selectedGateId)
    ?? gates.find((gate) => gate.status === "pending")
    ?? gates.find((gate) => !isInspectionGate(gate, traceByProposal.get(gate.proposal_id)))
    ?? gates[0]
    ?? null;
  const effectiveAnalytics = analyticsWithGateFallback(analytics, gates, demo?.session.id ?? null);
  const trustScore = effectiveAnalytics
    ? Math.round(effectiveAnalytics.trust_score.score * 100)
    : null;
  const apiHost = apiUrl.replace(/^https?:\/\//, "");
  const localGuardMode = isLocalApi(apiUrl);

  useEffect(() => {
    let mounted = true;
    fetch(`${apiUrl}/health`)
      .then((response) => {
        if (mounted) setHealth(response.ok ? "online" : "offline");
      })
      .catch(() => {
        if (mounted) setHealth("offline");
      });
    return () => {
      mounted = false;
    };
  }, [apiUrl]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlApi = params.get("api")?.trim();
    const nextApiUrl = urlApi || window.localStorage.getItem(ACTIVE_API_STORAGE_KEY) || DEFAULT_API_URL;
    if (urlApi) {
      window.localStorage.setItem(ACTIVE_API_STORAGE_KEY, urlApi);
      setApiUrl(urlApi);
    } else if (nextApiUrl !== apiUrl) {
      setApiUrl(nextApiUrl);
    }

    const urlSessionId = params.get("session")?.trim();
    if (urlSessionId) {
      window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, urlSessionId);
      setPinnedSessionId(urlSessionId);
      setActiveView("review");
    }

    const urlGateId = params.get("gate")?.trim();
    if (urlGateId) {
      setSelectedGateId(urlGateId);
      setActiveView("review");
    }

    const sessionId =
      urlSessionId
      || window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY);
    if (sessionId) void refreshSession(sessionId, nextApiUrl);
    void refreshRecentSessions(nextApiUrl);
  }, []);

  useEffect(() => {
    if (!demo?.session.id) return;
    const interval = window.setInterval(() => {
      void refreshSession(demo.session.id);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [apiUrl, demo?.session.id]);

  useEffect(() => {
    if (!localGuardMode) return;
    const interval = window.setInterval(() => {
      void attachLatestLocalSession();
    }, 2500);
    void attachLatestLocalSession();
    return () => window.clearInterval(interval);
  }, [apiUrl, demo?.session.id, localGuardMode, pinnedSessionId]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshRecentSessions(apiUrl);
    }, 5000);
    void refreshRecentSessions(apiUrl);
    return () => window.clearInterval(interval);
  }, [apiUrl]);

  useEffect(() => {
    setExplain(null);
    setExplainError(null);
  }, [selectedGateId]);

  async function refreshSession(sessionId: string, targetApiUrl = apiUrl) {
    try {
      const response = await fetch(`${targetApiUrl}/sessions/${sessionId}/timeline`);
      if (!response.ok) return;
      const timeline = (await response.json()) as TimelineResponse;
      window.localStorage.setItem(ACTIVE_API_STORAGE_KEY, targetApiUrl);
      window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, sessionId);
      setDemo({
        session: timeline.session,
        gates: timeline.gates,
        timeline: { traces: timeline.traces, gates: timeline.gates },
      });
      setSelectedGateId((current) => {
        const existing = timeline.gates.find((gate) => gate.id === current);
        const firstPending = timeline.gates.find((gate) => gate.status === "pending");
        if (!existing) {
          if (current && sessionId === demo?.session.id) return current;
          return firstPending?.id ?? timeline.gates[0]?.id ?? null;
        }
        if (existing.status !== "pending" && firstPending) return firstPending.id;
        return current;
      });
      setAnalytics(await fetchAnalytics(targetApiUrl, sessionId));
    } catch {
      return;
    }
  }

  async function attachLatestLocalSession() {
    if (pinnedSessionId) return;
    try {
      const response = await fetch(`${apiUrl}/sessions/latest`);
      if (!response.ok) return;
      const session = (await response.json()) as DemoResponse["session"];
      if (demo?.session.id === session.id) return;
      if (demo?.session.created_at && session.created_at) {
        const currentCreated = Date.parse(demo.session.created_at);
        const latestCreated = Date.parse(session.created_at);
        if (Number.isFinite(currentCreated) && Number.isFinite(latestCreated) && latestCreated <= currentCreated) {
          return;
        }
      }
      window.localStorage.setItem(ACTIVE_API_STORAGE_KEY, apiUrl);
      window.localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, session.id);
      await refreshSession(session.id, apiUrl);
    } catch {
      return;
    }
  }

  async function refreshRecentSessions(targetApiUrl = apiUrl) {
    try {
      const response = await fetch(`${targetApiUrl}/sessions?limit=12`);
      if (!response.ok) return;
      setRecentSessions((await response.json()) as SessionSummary[]);
    } catch {
      return;
    }
  }

  async function switchSession(sessionId: string, pinned = true) {
    if (!sessionId) return;
    setPinnedSessionId(pinned ? sessionId : null);
    setActiveView("review");
    await refreshSession(sessionId);
    await refreshRecentSessions(apiUrl);
  }

  async function followLatestSession() {
    setPinnedSessionId(null);
    try {
      const response = await fetch(`${apiUrl}/sessions/latest`);
      if (!response.ok) return;
      const session = (await response.json()) as SessionSummary;
      setActiveView("review");
      await refreshSession(session.id, apiUrl);
    } catch {
      return;
    }
  }

  async function sendSlackCards() {
    setSlackLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/demo/slack/send`, {
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
      const response = await fetch(`${apiUrl}/gates/${gate.id}/${action}`, {
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
      setAnalytics(await fetchAnalytics(apiUrl, updated.session_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit decision");
    }
  }

  async function explainGate(gate: Gate) {
    setExplainLoading(true);
    setExplainError(null);
    try {
      const response = await fetch(`${apiUrl}/gates/${gate.id}/explain`, { method: "POST" });
      if (!response.ok) throw new Error(`Explain failed with ${response.status}`);
      setExplain((await response.json()) as ExplainMoreResponse);
    } catch (err) {
      setExplainError(err instanceof Error ? err.message : "Unable to load explanation");
    } finally {
      setExplainLoading(false);
    }
  }

  const handleFlowGateSelect = useCallback((gateId: string) => {
    setSelectedGateId(gateId);
    setActiveView("review");
  }, []);

  return (
    <AppShell
      activeView={activeView}
      onView={setActiveView}
      health={health}
      apiHost={apiHost}
      recentSessions={recentSessions}
      activeSessionId={demo?.session.id ?? ""}
      pinnedSessionId={pinnedSessionId}
      slackChannel={slackChannel}
      slackLoading={slackLoading}
      onSwitchSession={(sessionId) => void switchSession(sessionId)}
      onFollowLatest={() => void followLatestSession()}
      onSlackChannel={setSlackChannel}
      onSendSlack={() => void sendSlackCards()}
    >
      {error ? <Notice tone="red">{error}</Notice> : null}
      {slackResult ? (
        <Notice tone="blue">
          Posted {slackResult.posted.length} Slack approval card
          {slackResult.posted.length === 1 ? "" : "s"} for session {slackResult.session_id.slice(0, 12)}.
        </Notice>
      ) : null}

      <MetricsStrip
        gates={gates}
        traces={traces}
        analytics={effectiveAnalytics}
        trustScore={trustScore}
        sessionId={demo?.session.id ?? null}
      />

      {activeView === "review" ? (
        <ReviewLedger
          demo={demo}
          gates={gates}
          traces={traces}
          selectedGate={selectedGate}
          traceByProposal={traceByProposal}
          analytics={effectiveAnalytics}
          trustScore={trustScore}
          apiUrl={apiUrl}
          localGuardMode={localGuardMode}
          decisionNote={decisionNote}
          explain={explain}
          explainLoading={explainLoading}
          explainError={explainError}
          onSelectGate={setSelectedGateId}
          onDecisionNote={setDecisionNote}
          onDecision={decide}
          onExplain={explainGate}
        />
      ) : null}
      {activeView === "flow" ? (
        <FlowMapView
          session={demo?.session ?? null}
          gates={gates}
          traces={traces}
          traceByProposal={traceByProposal}
          onSelectGate={handleFlowGateSelect}
        />
      ) : null}
      {activeView === "trajectory" ? (
        <TrajectoryView gates={gates} traces={traces} traceByProposal={traceByProposal} />
      ) : null}
      {activeView === "policies" ? <PolicyLedgerView gates={gates} apiUrl={apiUrl} /> : null}
      {activeView === "slack" ? (
        <SlackSurfaceView
          channel={slackChannel}
          result={slackResult}
          loading={slackLoading}
          onChannel={setSlackChannel}
          onSend={() => void sendSlackCards()}
        />
      ) : null}
      {activeView === "audit" ? (
        <AuditEventsView gates={gates} traces={traces} analytics={effectiveAnalytics} trustScore={trustScore} />
      ) : null}
    </AppShell>
  );
}

async function fetchAnalytics(apiUrl: string, sessionId: string) {
  const response = await fetch(`${apiUrl}/sessions/${sessionId}/analytics`);
  if (!response.ok) throw new Error(`Analytics failed with ${response.status}`);
  return (await response.json()) as LedgerAnalytics;
}
