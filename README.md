# AgentLens

AgentLens is a judgment layer for AI coding agents. It intercepts proposed tool calls, enriches them with codebase and session context, decides whether a human should review them, and records the full session in an audit-friendly ledger.

The first build is local-first: a simulator emits tool-call proposals through the same adapter interface that a real Codex integration will use later. This lets the risk, policy, OpenAI intelligence, approval, and ledger layers become useful before taking dependency on Codex-specific hooks.

## Current Architecture

- `backend/`: Python SDK and FastAPI service.
- `frontend/`: Next.js ledger shell.
- `examples/`: sample sessions and configs for local demos.
- `plan.md`: phased build and validation checklist.
- `implementation.md`: latest implementation status.
- `AGENTS.md`: instructions for Codex and other coding agents working on this repo.

## Backend Capabilities

- Start an AgentLens session with an original user instruction and repo path.
- Submit proposed tool calls through a stable internal schema.
- Capture append-only trace events with git status/diff snapshots.
- Evaluate ordered policies from `agentlens.config.yaml`.
- Score reversibility and blast radius with a deterministic baseline.
- Gate risky actions for local approval.
- Call real OpenAI structured-output intelligence for gated actions when `OPENAI_API_KEY` is configured.

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

6. Run the frontend review UI:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`, then click **Create Demo Session**. The UI creates a local
demo session, renders decision cards, and lets you approve, block, or modify pending gates.

7. Run the simulator demo:

```bash
cd backend
uv run agentlens-demo --fixture ../examples/demo_session.json
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
confidence, and translation output. Auto-executed low-risk actions use a lightweight
ledger card to avoid unnecessary model calls.

The local review UI uses `POST /demo/session` to create a sample session and decision
endpoints under `/gates/{id}` to approve, block, or modify pending gates.

## Environment Variables

- `OPENAI_API_KEY`: required for real intelligence integration tests and production intelligence calls.
- `OPENAI_MODEL`: chat/reasoning model for structured outputs.
- `OPENAI_EMBEDDING_MODEL`: embedding model for goal drift.
- `DATABASE_URL`: future PostgreSQL persistence target.
- `REDIS_URL`: future in-flight state/cache target.
- `SLACK_BOT_TOKEN`: future Slack approval surface.
- `SLACK_SIGNING_SECRET`: future Slack request verification.

## Status

See `implementation.md` for the current implementation state and `plan.md` for phase-by-phase acceptance gates.
