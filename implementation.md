# AgentLens Implementation Log

## Current Status

The repo is being initialized from `prd.md` into a local-first implementation. The first target is a working backend path for simulated tool-call interception, deterministic policy/risk decisions, local approvals, and real OpenAI intelligence calls when credentials are configured.

## Implemented

- Project documentation contract in `README.md`, `plan.md`, `implementation.md`, and `AGENTS.md`.
- Environment templates with `.env` ignored and `.env.example` committed.
- Backend package scaffold with typed schemas, trace capture, policy evaluation, risk scoring, intelligence interfaces, local approval endpoints, simulator, and tests.
- Frontend ledger shell scaffold.
- CLI simulator entrypoint with `agentlens-demo` and `examples/demo_session.json`.
- Backend tests and ruff checks pass after dependency sync.
- Real OpenAI integration test passes with `OPENAI_API_KEY` configured: `uv run pytest -m integration` selected 1 test and passed in 4.67s on June 21, 2026.
- Gated actions now build live OpenAI intelligence cards with trajectory prediction, embedding-based drift detection, calibrated confidence, and two-sentence translation.
- Auto-executed safe actions keep a lightweight deterministic ledger card to avoid unnecessary model calls.
- Frontend dependencies install and the Next.js ledger shell builds successfully.
- Local review UI can create a demo session through `POST /demo/session`, render decision cards, and approve/block/modify pending gates.
- Browser smoke verified the local UI: demo loads, `fs.delete` trace renders, approving a pending gate updates statuses to `AUTO EXECUTED`, `APPROVED`, and `PENDING`.
- Git snapshots are truncated at 12,000 characters in the initial trace engine to keep local UI/API payloads usable.
- Slack Block Kit rendering, request signature verification, and interactive action handling are implemented and tested.
- CLI can print Slack Block Kit payloads for pending gates with `uv run agentlens-demo --fixture ../examples/demo_session.json --slack`.
- Ledger analytics are implemented with `GET /sessions/{id}/analytics`.
- The frontend renders trust score, approval patterns, risk distribution, and drift history alongside the session timeline.
- Browser smoke verified analytics panels render and remain visible after approving a pending gate.
- Append-only JSONL audit persistence is implemented through `AGENTLENS_AUDIT_LOG_PATH`.
- `GET /audit/events` exposes recent audit entries for local demos.
- Codex CLI adapter seam is implemented with `codex exec --json --sandbox read-only`, including parser tests for tool-call JSONL events.
- CLI can run Codex preview mode with `uv run agentlens-demo --codex-prompt "..."`.
- Real Codex JSONL validation completed: `item.started` events with `item.type = command_execution` are parsed into `shell.run` proposals.
- Read-only Codex inspection commands now classify as low risk and auto-execute.
- Real Codex file-change validation completed in a disposable temp workspace: `item.started` events with `item.type = file_change` parse into `fs.write` / `fs.delete` proposals.
- PostgreSQL-ready SQLAlchemy models and repository seam are implemented in `agentlens.db`.
- Competition demo script and rubric checklist are available in `scripts/competition_demo.sh` and `docs/competition_demo.md`.
- Demo summaries are post-processed to plain ASCII English with bounded length and complete punctuation.
- Full competition demo script was verified end to end.
- Live Slack and PostgreSQL validation steps are documented in `docs/live_validation.md`.
- Slack Web API sender is implemented for posting pending gate cards to a real channel with `--slack-send-channel`.
- `POST /demo/slack/send` creates a backend-owned demo session and posts pending gate cards so Slack button clicks resolve against the running FastAPI store.
- Backend local verification passed after the Slack sender dependency fix: `uv run pytest -m 'not integration'` reported 28 passed, and `uv run ruff check .` passed.
- Live Slack validation passed on June 21, 2026: backend-owned demo cards posted to channel `C0BBW328TEF`, Slack button clicks reached `/integrations/slack/actions` through ngrok, and FastAPI returned `200 OK`.
- PostgreSQL-backed runtime storage is implemented behind `AGENTLENS_STORAGE_BACKEND=postgres`; sessions, traces, gates, and audit events are mirrored to SQLAlchemy repositories and reloaded into the runtime working set.
- Deployment prep is implemented with configurable CORS, provider Postgres URL normalization, `backend/Dockerfile`, `render.yaml`, `frontend/.env.example`, and `docs/deployment.md`.
- Hosted demo deployment is live on free tiers: backend `https://agentlens-api-ggkh.onrender.com`, frontend `https://frontend-ashy-mu-csvn2wfbmk.vercel.app`.
- Render backend `/health` passed, Vercel production deploy passed, and hosted CORS preflight passed for the Vercel frontend origin.

## Known Gaps

- Slack backend integration is implemented and live-validated through ngrok.
- PostgreSQL runtime storage is implemented but still needs live validation against a real managed Postgres instance.
- Redis remains a documented future target for in-flight state/cache, but it is not required for the hosted demo path yet.

## Next Steps

1. Validate `AGENTLENS_STORAGE_BACKEND=postgres` against a real local or hosted PostgreSQL instance.
2. Create or attach Render Postgres if the demo needs restart-proof persisted sessions; current hosted backend is running with in-memory state because Render CLI cannot create Postgres directly.
3. Update Slack Interactivity to the hosted backend URL and repeat the live button test.
4. Review the frontend npm audit finding before forcing dependency changes; the available audit fix is breaking.
