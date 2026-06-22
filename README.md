# AgentLens

AgentLens is a judgment layer for AI coding agents. It intercepts proposed tool calls, enriches them with codebase and session context, decides whether a human should review them, and records the full session in an audit-friendly ledger.

The current build is local-first: Codex can run normally in the terminal while project-local hooks mirror proposed tool calls into a local AgentLens guard. The hosted demo path remains available for judging, Slack validation, and remote review.

## Current Architecture

- `backend/`: Python SDK and FastAPI service.
- `frontend/`: Next.js hosted approval console.
- `examples/`: sample sessions and configs for local demos.
- `plan.md`: phased build and validation checklist.
- `implementation.md`: latest implementation status.
- `AGENTS.md`: instructions for Codex and other coding agents working on this repo.
- `docs/deployment.md`: hosted demo deployment checklist.

## Backend Capabilities

- Start an AgentLens session with an original user instruction and repo path.
- Submit proposed tool calls through a stable internal schema.
- Capture append-only trace events with git status/diff snapshots.
- Evaluate ordered policies from `agentlens.config.yaml`.
- Score reversibility and blast radius with a deterministic baseline.
- Gate risky actions for local approval.
- Call real OpenAI structured-output intelligence for gated actions when `OPENAI_API_KEY` is configured.
- Route lightweight summarization to a nano model while reserving the strong model for consequential gated actions.
- Explain decisions with trajectory, drift, confidence factors, dependency/reference evidence, and concise translation.

## Setup

1. Install dependencies:

```bash
cd backend
uv sync --extra dev
```

2. Add your OpenAI key:

```bash
cp ../.env.example ../.env
```

Then edit `.env` and replace `OPENAI_API_KEY=replace_me`.

3. Run backend tests:

```bash
cd backend
uv run pytest
```

If `OPENAI_API_KEY` is configured, the full test run includes real OpenAI integration tests.

4. Run only OpenAI integration tests:

```bash
cd backend
uv run pytest -m integration
```

5. Run the API locally:

```bash
cd backend
uv run uvicorn agentlens.api:app --reload
```

The health endpoint is `GET http://127.0.0.1:8000/health`.

6. Run AgentLens locally as a Codex guard:

```bash
cd backend
uv run agentlens-guard --repo /path/to/your/repo
```

This starts a local AgentLens API at `http://127.0.0.1:8787`, stores the ledger locally,
and keeps Codex execution on your machine.

7. Run Codex from your terminal while mirroring events into AgentLens:

```bash
cd backend
uv run agentlens-codex --repo /path/to/your/repo "What is this repo about?"
```

This runs Codex locally, prints readable terminal output, and mirrors parsed Codex
tool-call proposals into the local AgentLens dashboard. The command prints a dashboard
URL like `http://localhost:3000?session=ses_...&api=http%3A%2F%2F127.0.0.1%3A8787`;
open that URL to view the exact session created by the terminal run. The `api` query
parameter lets the frontend connect to the same local guard that received the mirrored
Codex events, even if the frontend was started without `NEXT_PUBLIC_AGENTLENS_API_URL`.

8. Run the frontend approval console against the local guard:

```bash
cd frontend
NEXT_PUBLIC_AGENTLENS_API_URL=http://127.0.0.1:8787 npm run dev
```

Open `http://localhost:3000`, then click **Start Supervision**. The UI starts a
local guarded Codex run, renders incoming Codex tool calls in the decision queue,
inspector, timeline, policy ledger, Slack surface, and audit views, and lets you approve,
block, or modify pending gates.

For a terminal-first local workflow, keep `agentlens-guard` and the frontend running,
then use `agentlens-codex` for each Codex task. This is the reliable integration path
today because it uses Codex JSON events. Attaching to an arbitrary already-running Codex
TUI session should be built against Codex's experimental app-server or remote-control
protocol, not by scraping terminal output.

### Normal Codex TUI Hook Mode

AgentLens also includes a project-local Codex hook config in `.codex/hooks.json`.
This lets normal interactive Codex sessions mirror tool-use events into the local
AgentLens guard without using `agentlens-codex`.
In local hook mode, AgentLens records risky Codex tool calls and can attempt to hold
pending gates while the dashboard records an approve, block, or modify decision. Treat
this TUI hook path as best-effort until each Codex tool event type is live-validated.

1. Start the local guard:

```bash
cd backend
uv run agentlens-guard --repo /Users/aaryan/Desktop/Agent_Lens
```

2. Start the frontend:

```bash
cd frontend
npm run dev
```

The dashboard can now use the `api` query parameter from terminal links, stored local
settings, or the default local API. It also polls `GET /sessions/latest` in local mode so
hook-created sessions can appear without a special dashboard link.

3. In a new terminal, run Codex normally from the repo root:

```bash
codex
```

If Codex says hooks need review, type `/hooks`, inspect the AgentLens hook commands, and
trust them for this project. After that, use Codex normally. `UserPromptSubmit` starts a
fresh AgentLens session for each new task, while `PreToolUse` and `PermissionRequest`
hook events are mirrored into AgentLens through the local
`backend/.venv/bin/agentlens-hook` console script, with a `uv run` fallback for fresh
checkouts. Duplicate hook notifications for the same tool payload are suppressed, and
local hook state is stored under `.agentlens/` and ignored by git.
If you restart `agentlens-guard`, the hook automatically creates a fresh AgentLens
session if the remembered local session no longer exists.

Read-only inspection commands are auto-executed and collapsed in the dashboard. For risky
hooked actions, the hook posts the proposal and can wait up to
`AGENTLENS_APPROVAL_TIMEOUT_SECONDS` seconds for an AgentLens decision. Approved,
modified, and auto-executed gates exit successfully; blocked or timed-out gates return a
non-zero hook exit. Normal Codex TUI behavior can vary by tool/event type, so use this as
best-effort enforcement until the specific path is validated. Set
`AGENTLENS_ENFORCE_APPROVALS=0` for mirror-only ledger behavior.

For hosted judging or remote viewing, start supervision in the web console, then run the
command shown in the empty review queue from your local checkout. It uses the Codex CLI
adapter to execute Codex locally, parse real Codex JSON events, and post proposed tool
calls into the hosted AgentLens session:

```bash
cd backend
uv run agentlens-demo \
  --api-url https://agentlens-api-ggkh.onrender.com \
  --session-id ses_... \
  --repo /path/to/your/repo \
  --codex-prompt "Inspect this repo and propose the next implementation step."
```

9. Run the simulator demo:

```bash
cd backend
uv run agentlens-demo --fixture ../examples/demo_session.json
```

To preview Slack Block Kit payloads for pending gates:

```bash
cd backend
uv run agentlens-demo --fixture ../examples/demo_session.json --slack
```

To post pending gate cards to a Slack channel after configuring `SLACK_BOT_TOKEN`:

```bash
cd backend
uv run agentlens-demo --fixture ../examples/demo_session.json --slack-send-channel C0123456789
```

For live button validation, prefer posting from the running backend so the clicked Slack
buttons resolve gates in the same server process:

```bash
curl -X POST http://127.0.0.1:8000/demo/slack/send \
  -H "Content-Type: application/json" \
  -d '{"channel_id":"C0123456789"}'
```

To run Codex CLI in read-only JSON mode and gate any parsed tool-call proposals:

```bash
cd backend
uv run agentlens-demo --codex-prompt "Inspect this repo and describe likely next steps."
```

## Local Demo Flow

1. Start the API.
2. Create a session with `POST /sessions`.
3. Submit a proposal with `POST /sessions/{id}/tool-calls`.
4. Inspect pending gates with `GET /gates/pending`.
5. Approve, block, modify, or explain the gate.
6. Review the timeline with `GET /sessions/{id}/timeline`.

For a faster CLI-only check, run `uv run agentlens-demo --fixture ../examples/demo_session.json`
from `backend/`.

With `OPENAI_API_KEY` configured, gated demo actions produce live trajectory, drift,
confidence, dependency evidence, and translation output. Auto-executed low-risk actions
use a lightweight ledger card to avoid unnecessary model calls.

## Intelligence Layer and Model Routing

AgentLens builds a typed decision context for each proposal: original instruction,
recent traces, prior gate summaries, git snapshot, policy decision, semantic risk, and
dependency/reference evidence. Gated actions use that context to produce:

- Counterfactual trajectory with likely next steps and a commitment point.
- Embedding-based goal drift score.
- Confidence calibration factors that show why confidence moved up or down.
- Dependency evidence from Python and JavaScript/TypeScript imports plus config/docs references.
- A concise approval-card summary for Slack and the web inspector.

`OPENAI_MODEL` is the strong model for consequential actions. `OPENAI_NANO_MODEL` is used
for cheaper summaries or low-risk work. Embeddings still use `OPENAI_EMBEDDING_MODEL`.
This keeps the max-intelligence path available without spending strong-model calls on
simple read-only inspection.

The review console uses `POST /demo/session` to create a sample session and decision
endpoints under `/gates/{id}` to approve, block, or modify pending gates.

The ledger also calls `GET /sessions/{id}/analytics` to show:

- Trust score: actions completed without human intervention.
- Approval patterns: gate status counts.
- Risk distribution: low/medium/high/critical counts.
- Drift history: gated actions with drift flags.

## Slack Integration

AgentLens exposes `POST /integrations/slack/actions` for Slack Block Kit interactions.
It verifies `X-Slack-Signature` and `X-Slack-Request-Timestamp` using
`SLACK_SIGNING_SECRET`, then maps button actions to the existing gate decision flow.
For local live validation, `POST /demo/slack/send` creates a backend-owned demo session
and posts pending cards to a real Slack channel.

Supported Slack action IDs:

- `approve_gate`
- `block_gate`
- `modify_gate`
- `explain_gate`

The message renderer lives in `agentlens.slack.render_gate_message`. Use the CLI
`--slack` flag to preview the payload before wiring a real Slack app.

## Codex Adapter

The Codex adapter uses `codex exec --json --sandbox read-only` and treats parsed
`item.started` / `command_execution` JSONL events as AgentLens `shell.run` proposals.
Read-only shell inspection commands such as `pwd`, `rg`, `find`, `sed`, `sort`, and safe
`git` inspection commands are classified as low risk and auto-executed.

For controlled validation in disposable workspaces, the CLI also accepts:

```bash
uv run agentlens-demo --repo /private/tmp/agentlens-codex-fixture \
  --codex-sandbox workspace-write \
  --codex-prompt "Create a harmless probe file."
```

Real Codex `item.started` / `file_change` events are parsed into `fs.write` or `fs.delete`
proposals based on each change kind.

## Audit Log

AgentLens writes append-only JSONL audit events to `AGENTLENS_AUDIT_LOG_PATH`.
Current event types:

- `session_started`
- `trace_captured`
- `gate_created`
- `gate_updated`

Use `GET /audit/events?limit=100` to inspect recent records during local demos.

## Database Layer

`agentlens.db` defines PostgreSQL-ready SQLAlchemy models for:

- `agentlens_sessions`
- `agentlens_traces`
- `agentlens_gates`
- `agentlens_audit_events`

Runtime state can use the in-memory store for local fallback or PostgreSQL for durable
hosted state with `AGENTLENS_STORAGE_BACKEND=postgres`.

## Environment Variables

- `OPENAI_API_KEY`: required for real intelligence integration tests and production intelligence calls.
- `OPENAI_MODEL`: chat/reasoning model for structured outputs.
- `OPENAI_NANO_MODEL`: cheaper chat/reasoning model for lightweight summaries and low-risk work.
- `OPENAI_EMBEDDING_MODEL`: embedding model for goal drift.
- `DATABASE_URL`: PostgreSQL persistence target when `AGENTLENS_STORAGE_BACKEND=postgres`.
- `REDIS_URL`: future in-flight state/cache target.
- `SLACK_BOT_TOKEN`: Slack bot token for posting approval cards.
- `SLACK_SIGNING_SECRET`: Slack request verification secret.
- `SLACK_CHANNEL_ID`: default Slack channel for backend-owned demo cards.
- `AGENTLENS_AUDIT_LOG_PATH`: local append-only JSONL audit log path.
- `AGENTLENS_STORAGE_BACKEND`: `memory` for local fallback or `postgres` for hosted durable state.
- `AGENTLENS_CORS_ORIGINS`: comma-separated frontend origins allowed to call the backend.
- `AGENTLENS_PROJECT_ROOT`: repo path used by hosted demo sessions and risk/dependency scanning.
- `AGENTLENS_ENFORCE_APPROVALS`: `1` to make Codex hooks fail blocked/timed-out gates, `0` for mirror-only mode.
- `AGENTLENS_APPROVAL_TIMEOUT_SECONDS`: seconds a hook waits for a pending dashboard decision.

## Status

See `implementation.md` for the current implementation state and `plan.md` for phase-by-phase acceptance gates.

## Competition Demo

Run the local verification and demo preview:

```bash
./scripts/competition_demo.sh
```

The judging script and rubric mapping live in `docs/competition_demo.md`.

For live Slack/PostgreSQL validation steps, use `docs/live_validation.md`.

For hosted judging deployment, use `docs/deployment.md`. The intended demo setup is a
public backend with PostgreSQL enabled plus a public Vercel frontend configured with
`NEXT_PUBLIC_AGENTLENS_API_URL`.
