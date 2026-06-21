# AgentLens Competition Demo

This demo is designed to show AgentLens against the judging rubric: challenge-solution fit,
AI leverage, product thinking/UI, originality, and evidence of real demand.

## Demo Story

AgentLens sits between Codex and execution. It captures proposed tool calls, scores risk with
repo context, predicts likely next steps, detects drift, translates the action into developer
language, and pushes the decision into a local review UI or Slack-style card.

## Demo Script

1. Start the backend:

```bash
cd backend
uv run uvicorn agentlens.api:app --reload
```

2. Start the frontend:

```bash
cd frontend
npm run dev
```

3. Open `http://localhost:3000` and click **Create Demo Session**.

4. Show the three core moments:

- Safe read: `fs.read` auto-executes with low risk.
- Risky write: `fs.write` requires review with trajectory, drift, confidence, and evidence.
- Migration delete: `fs.delete` is critical because migrations are protected.

5. Approve or block one pending gate in the UI.

6. Show ledger analytics:

- Trust score.
- Approval patterns.
- Risk distribution.
- Drift history.

7. Show Slack preview:

```bash
cd backend
uv run agentlens-demo --fixture ../examples/demo_session.json --slack
```

8. Show audit trail:

```bash
curl http://127.0.0.1:8000/audit/events?limit=5
```

9. Optional Codex adapter validation:

```bash
cd backend
uv run agentlens-demo --codex-prompt "Do not modify files. Inspect the repository at a high level and answer with the names of the top-level files/directories you used. Keep it brief."
```

## Rubric Mapping

### Challenge-Solution Fit

AgentLens directly addresses unsafe autonomous coding-agent execution. The demo shows the
difference between a safe read, a reviewable write, and a critical destructive migration action.

### AI Leverage and Technical Execution

The system uses real OpenAI structured outputs for trajectory and translation, embeddings for
goal drift, codebase-aware risk scoring, Codex JSONL event parsing, Slack signing, and audit logs.

### Product Thinking and UI/UX

The local review UI is built around fast decisions: summary, risk, confidence, trajectory, drift,
policy, and action buttons are visible in one card. The ledger is secondary and focuses on replay
and trust patterns.

### Originality and Insight

AgentLens does not ask "approve this command?" in isolation. It asks whether the agent should
continue in a direction by showing likely next steps and the point where the action becomes harder
to undo.

### Evidence of Real Demand

The PRD identifies a concrete supervision gap for coding agents: irreversible actions, goal drift,
opaque reasoning, and approval fatigue. The demo shows a workflow a developer can actually use
without monitoring a dashboard.

## Validation Commands

Run the full local verification:

```bash
./scripts/competition_demo.sh
```

Expected:

- Backend tests pass.
- Backend lint passes.
- Frontend build passes.
- CLI demo emits low-risk auto-execution and gated medium/critical actions.
- Slack preview emits Block Kit payloads.

## Live-Service Follow-Up

For a production-like rehearsal, configure these external services after the local demo is stable:

- Slack app: point Interactivity to `/integrations/slack/actions` through a public tunnel.
- PostgreSQL: use `DATABASE_URL` and the SQLAlchemy models in `agentlens.db`.
- Codex: run the read-only adapter preview, then the disposable workspace-write probe.
