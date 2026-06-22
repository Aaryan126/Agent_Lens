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
- Hosted Render Postgres is provisioned: `agentlens-db` (`dpg-d8rtkbe7r5hc73epfmpg-a`), free plan, Singapore region, expires on July 21, 2026.
- Hosted backend now runs with `AGENTLENS_STORAGE_BACKEND=postgres`; hosted demo session creation passed, audit events were present after a Render service restart, confirming persisted runtime state.
- Hosted Slack validation passed after deploying explicit `chat.update` handling: Slack Approve / Block / Modify clicks reach the hosted backend, update persisted gate state, and visually replace the Slack message with resolved status/buttons removed.
- Hosted frontend was redesigned from a minimal validation shell into a richer command-center demo with runtime status, hosted Slack send controls, proof points, richer decision cards, analytics, timeline, and a meaningful empty state.
- Production Vercel smoke passed after the redesign: backend status rendered online, Create Session loaded 3 decision cards, analytics rendered, and no horizontal overflow was detected at 1440px width.
- Final frontend polish pass replaced the marketing-style demo page with a production-style operator console: persistent dark sidebar, compact topbar controls, status metrics, decision queue table, right-side inspector, timeline, and ledger analytics.
- The frontend revamp is deployed at `https://frontend-ashy-mu-csvn2wfbmk.vercel.app` and was smoke-tested against the hosted Render backend: backend status rendered online, `Run Demo Session` created a real session, queue/inspector/analytics populated, and no horizontal overflow was detected at 1440px desktop or 390px mobile widths.
- The hosted console main workspace was tightened again for production presentation: controlled max width, compact metric cards, aligned review grid, smaller inspector empty state, and working sidebar sections for Trajectory, Policy Ledger, Slack Surface, and Audit Events.
- The primary UI flow now presents itself as a real supervision workflow rather than a toy demo: the public console uses `Live Review`, `Start Supervision`, and Codex-action waiting states.
- Start Supervision now creates an empty real AgentLens session through `POST /sessions` and polls the timeline instead of replaying the fixture. The empty queue shows a session-specific adapter command for posting real local Codex CLI events into the hosted review queue.
- The CLI supports remote posting with `--api-url` and `--session-id`, so `uv run agentlens-demo --codex-prompt ...` can run Codex locally and submit parsed tool-call proposals to the hosted backend.
- Local-first guard mode is implemented with `uv run agentlens-guard --repo ...`. It starts a local API on `127.0.0.1:8787`, keeps storage local by default, and lets the frontend call `/codex/sessions` so Codex runs on the developer's machine instead of in the hosted backend.
- `POST /codex/sessions` runs the Codex CLI adapter locally, parses real Codex JSON events, gates the resulting proposals, and returns the same timeline/ledger shape as the hosted session API.
- Terminal-first Codex mirroring is implemented with `uv run agentlens-codex --repo ... "task"`. It creates or uses an AgentLens session, runs Codex locally, prints readable terminal output, and mirrors parsed tool-call proposals into the AgentLens API.
- The frontend review queue and timeline now collapse low-risk auto-executed inspection calls into a single inspection batch so read-only exploration does not flood the dashboard.
- Latest hosted smoke passed: every sidebar section switched content, `Start Supervision` created a real hosted session, remote CLI posting populated the review queue, and no horizontal overflow was detected on desktop or mobile.
- Terminal-first mirroring now prints a session-specific dashboard URL, and the frontend loads `?session=...` links directly. This fixes the gap where `agentlens-codex` successfully posted events to the local guard but the browser stayed on an old or empty session.
- Codex CLI surface review found experimental `app-server`, `remote-control`, and `exec-server` commands, but no stable first-pass command for subscribing to an arbitrary already-open Codex TUI session. The reliable path remains launching Codex through AgentLens JSON event mode; deeper always-on attachment should target the official Codex server protocol.
- Terminal session links now include both `session` and `api` query parameters, and the frontend can switch API targets at runtime. This fixes local dashboards that were started without `NEXT_PUBLIC_AGENTLENS_API_URL=http://127.0.0.1:8787`.
- A first native Codex TUI integration is implemented through project-local hooks in `.codex/hooks.json` and the `agentlens-hook` console script. Normal interactive Codex sessions can mirror `PreToolUse` and `PermissionRequest` events into the local AgentLens guard after the user reviews/trusts the hooks with `/hooks`.
- The local API now exposes `GET /sessions/latest`, and the local frontend polls it so hook-created sessions can appear without a session-specific URL.
- `agentlens-hook` now recovers when `.agentlens/codex_hook_session.json` points at a session from a previous in-memory guard process. A `404 session not found` response triggers fresh session creation and a retry.
- The dashboard no longer shows the web-launched Codex task composer. The primary local workflow is now the normal Codex terminal plus project hooks, with the UI acting as a passive review and ledger console.
- Cost-aware OpenAI model routing is implemented through `agentlens.model_routing`. Low-risk auto-executed work and lightweight summaries use `OPENAI_NANO_MODEL`; consequential gated actions use `OPENAI_MODEL`; drift continues to use `OPENAI_EMBEDDING_MODEL`.
- Decision cards now carry full trajectory details, confidence calibration factors, dependency/reference evidence, drift score, and model-role metadata. The frontend inspector renders those details so the dashboard shows why AgentLens made a recommendation instead of only showing a risk badge.
- The intelligence layer now receives a typed `DecisionContext` containing the original instruction, recent trace/gate context, git snapshot, risk, policy, inferred goal, and dependency evidence before generating trajectory, drift, confidence, and translation.
- Semantic risk analysis now scans Python plus JavaScript/TypeScript import references, config/docs references, affected shell paths, and shell mutation evidence.
- `POST /gates/{gate_id}/explain` now returns structured `ExplainMoreResponse` data with trajectory, confidence evidence, dependency evidence, and safer modification guidance. Slack `Explain more` renders the richer explanation too.
- Codex hook mode now handles `UserPromptSubmit` to create a fresh AgentLens session per new Codex task and suppresses duplicate hook notifications for the same tool payload across `PreToolUse` and `PermissionRequest`.
- Validation passed on June 22, 2026: focused backend suite `uv run pytest tests/test_policy_risk.py tests/test_session_api.py tests/test_codex_hook.py tests/test_model_routing.py tests/test_openai_integration.py` reported 26 passed, `uv run ruff check .` passed, and frontend `npm run build` passed.
- Live Codex TUI validation exposed `PreToolUse hook timed out after 10s` when many hooks fired through `uv run agentlens-hook`. `.codex/hooks.json` now prefers the already-installed `backend/.venv/bin/agentlens-hook` console script, keeps a `uv run` fallback, and raises hook timeouts to 30 seconds. Hook JSON validation passed and `uv run pytest tests/test_codex_hook.py` reported 5 passed.
- Read-only shell and file inspections now short-circuit to low risk before dependency/config blast-radius checks. This prevents repo overview tasks from creating pending gates just because they read important files such as `api.py`, `session.py`, or `package.json`.
- Hook mode now has first-pass enforcement. `agentlens-hook` posts a proposal, allows auto-executed gates, exits non-zero for blocked gates, and waits up to `AGENTLENS_APPROVAL_TIMEOUT_SECONDS` for pending gates to be approved/modified in the dashboard. `AGENTLENS_ENFORCE_APPROVALS=0` keeps mirror-only behavior for troubleshooting.
- The frontend inspector now labels buttons as gate decisions and explains that local hook mode waits briefly for approval, block, or timeout.
- Validation passed after enforcement changes: `uv run pytest` reported 57 passed, `uv run ruff check .` passed, and frontend `npm run build` passed.

## Known Gaps

- Slack backend integration is implemented and live-validated through ngrok.
- PostgreSQL runtime storage is implemented and live-validated against Render Postgres.
- Redis remains a documented future target for in-flight state/cache, but it is not required for the hosted demo path yet.
- Codex hook payload shapes have been hardened against the observed local flow, but broader MCP/edit-tool payload variants should still be collected from more live sessions.
- Deep attachment to an arbitrary already-running Codex TUI should still target Codex's app-server/remote-control protocol when that surface stabilizes.

## Next Steps

1. Warm `https://agentlens-api-ggkh.onrender.com/health` before judging because Render free web services sleep after idle.
2. Renew or upgrade Render Postgres before July 21, 2026 if the demo must remain live.
3. Re-trust the updated Codex hooks with `/hooks`, then run one fresh live Codex TUI session and confirm read-only inspection collapses without pending gates.
4. Ask Codex for a small file edit, approve it in AgentLens within the timeout, and confirm Codex continues.
5. Ask Codex for a destructive action, block it in AgentLens, and confirm Codex does not execute it.
6. Capture additional hook payload shapes for apply_patch, Edit/Write, and MCP tools to improve normalization.
7. Investigate Codex's app-server protocol for a deeper future integration that can stream turn/item events with richer state than hooks.
8. Review the frontend npm audit finding before forcing dependency changes; the available audit fix is breaking.
