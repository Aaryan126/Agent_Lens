# AgentLens Plan

## Phase 0: Foundation

Build repo hygiene, documentation, backend package, frontend shell, environment templates, and a health check.

Automatic validation:
- Backend imports.
- Schema serialization tests.
- FastAPI health test.

Human validation:
- Setup works from `README.md`.
- `.env` remains ignored.
- Phase docs explain what exists and what comes next.

Status: complete for the initial scaffold.

## Phase 1: Trace Engine and Simulator

Build `AgentLensSession`, a simulator, append-only trace events, and git snapshot capture.

Automatic validation:
- Trace capture tests.
- Git status/diff snapshot tests.
- Simulator replay tests.

Human validation:
- Run a sample session and inspect the timeline.

Status: complete for the initial simulator path.

## Phase 2: Policy and Risk

Build ordered config policies, reversibility scoring, blast-radius scoring, and gate decisions.

Automatic validation:
- Policy precedence tests.
- Safe read auto-approval tests.
- Destructive migration escalation tests.
- Dependency blast-radius fixture tests.

Human validation:
- Review sample decisions for intuitive risk classification.

Status: complete for deterministic baseline risk and policy decisions.

## Phase 3: Real OpenAI Intelligence

Build typed OpenAI calls for trajectory, drift, confidence, and translation. Tests use real OpenAI credentials when configured.

Automatic validation:
- Real structured-output integration test.
- Real embedding drift test.
- Malformed response handling tests.

Human validation:
- Approval card summaries are clear in under 10 seconds.

Status: complete for first implementation. Gated actions now generate real trajectory,
embedding-based drift, calibrated confidence, and OpenAI translation cards.

## Phase 4: Local Approval Surface

Build pending gates, approve, block, modify, and explain-more endpoints.

Automatic validation:
- Decision API tests.
- Idempotency tests.
- Simulator resume/halt tests.

Human validation:
- Approve/block/modify at least 3 demo actions locally.

Status: complete for local demo review. The Next.js UI can create a demo session, render
decision cards, and approve/block/modify pending gates through the FastAPI backend.

## Phase 5: Slack Approval Surface

Build Slack Block Kit cards, signing verification, and interactive button handlers.

Automatic validation:
- Card snapshot tests.
- Signature verification tests.
- Idempotency tests.

Human validation:
- Run one Slack approval demo with credentials.

Status: complete and live-validated. Block Kit rendering, signature verification,
approve/block/modify/explain handling, CLI payload preview, Slack Web API posting, and
backend-owned demo card posting are implemented. On June 21, 2026, Slack button clicks
reached `/integrations/slack/actions` through ngrok and returned `200 OK`.

## Phase 6: Session Ledger

Build timeline replay, approval patterns, drift history, and trust score.

Automatic validation:
- API contract tests.
- Frontend smoke tests.
- Playwright timeline test.

Human validation:
- Replay one full demo session.

Status: complete for first implementation. The backend exposes `GET /sessions/{id}/analytics`,
and the local ledger renders trust score, approval patterns, risk distribution, and drift
history alongside the timeline.

## Phase 7: Codex Adapter and Competition Polish

Wire the real Codex adapter after simulator behavior is stable.

Automatic validation:
- Codex adapter smoke test.
- Simulator regression suite.
- Real OpenAI integration suite.

Human validation:
- Run the final judging demo against the rubric in `prd.md` and the supplied judging criteria.

Status: mostly complete for local competition demo. AgentLens now has an append-only JSONL audit log,
`GET /audit/events`, PostgreSQL-ready SQLAlchemy ledger models, and a Codex CLI adapter.
Real Codex JSONL validation confirmed `command_execution` and `file_change` parsing.
Read-only Codex inspection commands auto-execute as low risk, while file changes become
`fs.write` / `fs.delete` proposals. The final local demo script and rubric checklist are
implemented. Remaining work: wire PostgreSQL-backed runtime state.

## Phase 8: Hosted Judging Demo

Make AgentLens deployable behind stable public URLs so judges can use a live link without
local backend, frontend, ngrok, or Slack tunnel setup.

Automatic validation:
- Backend container builds.
- Backend tests pass with the PostgreSQL storage backend code path covered by repository tests.
- Frontend build passes with `NEXT_PUBLIC_AGENTLENS_API_URL` configured.
- Hosted `/health` returns `200 OK`.

Human validation:
- Open the public frontend URL and create a demo session.
- Post Slack demo cards from the public backend.
- Click Slack Approve / Block / Modify and confirm cards update.
- Confirm sessions survive backend restart when PostgreSQL is enabled.

Status: complete for the hosted judging demo path. Deployment docs, backend Dockerfile,
Render backend, Render Postgres, Vercel frontend, configurable CORS, PostgreSQL URL
normalization, Slack hosted interactivity, and PostgreSQL-backed runtime storage are
implemented and live-validated. The public frontend was smoke-tested against the hosted
backend after the operator-console redesign.

## Phase 9: Local-First Guard

Make AgentLens useful as a local developer tool rather than a cloud-first demo. The guard
runs on the developer machine, starts a local API, stores the ledger locally by default,
and executes Codex locally so repository context does not need to leave the workstation.

Automatic validation:
- Guard command imports and starts through the packaged console script.
- `/codex/sessions` API test stubs the Codex adapter and verifies parsed proposals are gated.
- Frontend build passes with local API mode logic.

Human validation:
- Run `uv run agentlens-guard --repo .`.
- Start the frontend with `NEXT_PUBLIC_AGENTLENS_API_URL=http://127.0.0.1:8787 npm run dev`.
- Submit a Codex task from the UI and confirm the local dashboard shows intercepted actions.

Status: first implementation complete. `agentlens-guard` starts the local API on
`127.0.0.1:8787`; `/codex/sessions` runs the local Codex CLI adapter and gates parsed
tool-call proposals; the frontend detects local API mode and calls the local Codex
endpoint instead of the hosted bridge flow.

Follow-up status: terminal-first mirroring is implemented with `agentlens-codex`, letting
developers run Codex from their normal terminal while AgentLens mirrors parsed tool calls
into the dashboard. Low-risk inspection calls are collapsed in the review queue and
timeline to keep the dashboard focused on meaningful supervision events. The terminal
command now prints a session-specific dashboard URL, and the frontend restores sessions
from `?session=...`, so locally mirrored Codex runs appear immediately in the dashboard.
Further work should investigate Codex's experimental app-server / remote-control protocol
before promising attachment to an arbitrary already-open Codex TUI session.

Second follow-up status: first native Codex TUI attachment is implemented through
project-local Codex hooks. `.codex/hooks.json` mirrors `PreToolUse` and
`PermissionRequest` events into the local guard through `agentlens-hook`, while the local
frontend polls `/sessions/latest` so hook-created sessions appear without a dashboard
link. This still needs live interactive validation and payload-shape hardening before it
should be presented as the primary production path.

Third follow-up status: Codex hook mode is now stronger for real usage. `UserPromptSubmit`
starts a fresh AgentLens session per task, duplicate `PreToolUse` / `PermissionRequest`
payloads are suppressed, stale local session files recover automatically, and the web
task composer has been removed so the normal Codex terminal remains the primary workflow.
Live validation then exposed hook process startup latency: repeated `PreToolUse` calls
timed out at Codex's 10-second hook limit when routed through `uv run`. The project hook
commands now prefer `backend/.venv/bin/agentlens-hook`, keep a `uv run` fallback, and use
a 30-second timeout.
Fourth follow-up status: hook mode is no longer mirror-only for pending risky actions.
Read-only shell/file inspections short-circuit to low risk and auto-execute before
dependency blast-radius checks. Pending hooked actions wait briefly for AgentLens
approval; approved/modified gates pass, blocked or timed-out gates fail the hook with a
non-zero exit. The UI now labels these controls as gate decisions instead of generic
Codex controls.
Live validation confirmed the read-only collapse, but a normal Codex TUI README edit
executed before a dashboard decision. Hook-mode enforcement is therefore documented as
best-effort and tool/event dependent until apply_patch/Edit/Write paths are validated or
replaced with an app-server based pause/resume integration. The inspector now hides
decision controls for resolved gates and auto-focuses pending gates.

## Phase 10: Intelligence Depth and Cost-Aware Routing

Make the intelligence layer match the PRD more closely while using OpenAI calls
efficiently. Reserve the strong model for consequential gated decisions, use the nano
model for lightweight summaries and low-risk work, and expose the reasoning evidence in
the approval surfaces.

Automatic validation:
- Model routing tests prove low-risk auto-executed work uses the nano role and gated writes use the strong role.
- Risk tests cover JavaScript/TypeScript import references, config/doc references, and destructive shell evidence.
- Session/API tests cover richer explain responses.
- Hook tests cover prompt-created sessions and duplicate hook suppression.
- Real OpenAI integration tests cover structured trajectory and full card generation.
- Frontend production build validates the expanded card schema.

Human validation:
- Start `uv run agentlens-guard --repo /Users/aaryan/Desktop/Agent_Lens`.
- Start the frontend on `localhost:3000`.
- Run a normal Codex TUI task and confirm AgentLens starts a fresh session from the prompt.
- Confirm the inspector shows trajectory, dependency evidence, confidence calibration, drift, and model routing.
- Trigger a duplicated permission/tool event and confirm the dashboard does not show duplicate rows for the same action.

Status: implementation complete for the first cost-aware intelligence pass. Decision
cards now carry full trajectory, confidence factors, dependency/reference evidence,
drift score, and model-role metadata. `Explain More` returns the same structured
evidence through the API and Slack. Validation passed on June 22, 2026: focused backend
suite `26 passed`, real OpenAI integration tests passed, `uv run ruff check .` passed,
and `npm run build` passed. After the hook timeout fix, `.codex/hooks.json` parsed
successfully and `uv run pytest tests/test_codex_hook.py` passed. After hook enforcement
and read-only risk fixes, `uv run pytest` reported 57 passed, `uv run ruff check .`
passed, and frontend `npm run build` passed. After live TUI validation, the UI was
tightened to hide resolved-gate controls and the docs were corrected to avoid
overpromising hard pre-execution enforcement for every normal TUI tool path.
