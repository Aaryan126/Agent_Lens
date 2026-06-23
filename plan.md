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

Fifth follow-up status: hook mode has been moved back to observability-first by default.
Live native TUI testing showed `PreToolUse` and `PermissionRequest` hook timeouts after
30 seconds while Codex still applied a README edit. Hook-originated proposals now use a
fast deterministic card path instead of full OpenAI trajectory generation, and
`.codex/hooks.json` sets `AGENTLENS_ENFORCE_APPROVALS=0` so normal Codex sessions do not
hang on dashboard polling. Strict approval control is Phase 11/12 app-server work.

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

## Phase 11: Guarded App-Server Terminal

Make strict local control practical by launching Codex through AgentLens instead of
trying to hard-block every arbitrary already-open TUI event. The guarded terminal uses
Codex app-server's JSON-RPC approval callbacks for command and file-change requests,
turns each callback into an AgentLens proposal, waits for dashboard decisions when the
gate is pending, and returns accept/cancel responses to Codex.

Automatic validation:
- JSON-RPC adapter tests cover initialize, thread start, turn start, approval request handling, and turn completion.
- Approval bridge tests verify pending AgentLens gates are polled until approved.
- Existing Codex CLI, session API, hook, policy/risk, and model-routing tests remain green.
- Backend ruff passes.

Human validation:
- Start `uv run agentlens-guard --repo /Users/aaryan/Desktop/Agent_Lens`.
- Start the frontend on `localhost:3000`.
- Run `uv run agentlens-run --repo /Users/aaryan/Desktop/Agent_Lens`.
- Enter a read-only repo inspection task and confirm low-risk callbacks auto-execute/collapse.
- Enter a small write task and confirm Codex waits for the AgentLens dashboard decision before the app-server approval response is sent.
- Block one pending write and confirm Codex receives a cancel decision and does not continue that action.

Status: first implementation in progress. `agentlens-run` now starts a terminal-first
Codex app-server turn, creates an AgentLens session, maps command/file-change/permission
approval callbacks into `ToolCallProposal` records, and returns accept/cancel responses
based on AgentLens gate decisions. Permission-profile grants are conservative until live
validated against more app-server payloads.

Follow-up status: multi-terminal session control is implemented. The API exposes
`GET /sessions` for recent sessions, and the frontend header now has a session picker plus
explicit Follow Latest mode. Session URLs printed by `agentlens-run` pin the dashboard to
that terminal's session so hook-created or newer terminal sessions cannot silently steal
approval focus. Gate-specific review URLs now add `?gate=...`, and the frontend selects
that exact gate so users can approve the action a waiting terminal is polling.
Second follow-up status: terminal-native approvals are implemented for `agentlens-run`.
Pending app-server gates can now be approved, blocked, or modified directly in the terminal,
while the dashboard remains available for detailed inspection. Dashboard session locks are
persisted in localStorage until Follow Latest is clicked, so multiple Codex terminals cannot
silently steal focus from a pinned approval session.

## Phase 12: Native Codex TUI App-Server Proxy

Explore the production path that keeps Codex's polished native TUI while routing its
app-server approval traffic through AgentLens. The proxy sits between `codex --remote`
and `codex app-server`, converts approval requests into AgentLens gates, records native
approve/cancel responses back into the ledger, and enriches native approval prompts with
AgentLens risk summaries while keeping dashboard URLs in structured AgentLens metadata.

Automatic validation:
- Proxy state tests cover session creation from `turn/start`.
- Proxy approval tests cover pending gate enrichment, auto-executed accept responses, and
  native approve/cancel decisions being written back to AgentLens.
- Existing app-server adapter tests remain green.
- Backend ruff passes.

Human validation:
- Start `uv run agentlens-guard --repo /Users/aaryan/Desktop/Agent_Lens`.
- Start the frontend on `localhost:3000`.
- Start `uv run agentlens-codex-proxy --repo /Users/aaryan/Desktop/Agent_Lens`.
- Connect a real Codex TUI with `AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted --sandbox workspace-write --remote ws://127.0.0.1:8791`.
- Run a read-only task and confirm low-risk approvals enter the AgentLens ledger without
  interrupting Codex.
- Run a second prompt in the same Codex TUI session and confirm the proxy forwards
  follow-up `turn/start` messages without crashing the TUI.
- Confirm the dashboard keeps those follow-up prompts grouped under the same AgentLens
  session and follows the active local session unless manually pinned.
- Run a small README write and confirm the native Codex approval prompt appears while the
  AgentLens dashboard shows the matching pending gate.
- Approve one native prompt and confirm the AgentLens ledger records the same decision.

Status: first implementation complete for the local proxy spike. `agentlens-codex-proxy`
starts a local Codex app-server, exposes a WebSocket endpoint for `codex --remote`,
intercepts app-server approval requests, posts them to AgentLens, returns automatic
accept/cancel responses for resolved gates, forwards pending approvals to the native TUI
with AgentLens context, and records native approve/cancel responses back to the ledger.
The remaining uncertainty is UI depth: Codex's native TUI may only render the standard
approval fields, so rich AgentLens cards still live in the dashboard unless a future Codex
extension point or fork exposes a first-class native card surface.

Final validation status: Phase 12 human validation passed for the native approve path.
The local guard ran on `127.0.0.1:8787`, the frontend connected to that local guard, and
`agentlens-codex-proxy` ran on `ws://127.0.0.1:8791`. Codex launched successfully with
`AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted --sandbox workspace-write --remote ws://127.0.0.1:8791`.
A read-only prompt produced auto-executed ledger entries. A README edit prompt triggered
the native Codex approval prompt with AgentLens reason copy, and approving in Codex allowed
the README edit. Automated validation passed after clearing the live proxy
`AGENTLENS_DISABLE_HOOKS=1` environment for hook unit tests:
- `env -u AGENTLENS_DISABLE_HOOKS uv run pytest` reported 73 passed with 1 warning.
- `env -u AGENTLENS_DISABLE_HOOKS uv run pytest tests/test_codex_proxy.py tests/test_codex_app_server.py` reported 14 passed.
- `./.venv/bin/ruff check .` passed.
- Frontend `npm run build` passed.

Follow-up validation status: native proxy block/cancel was also manually validated with a
README edit prompt. Blocking in the native Codex prompt prevented the edit and the
AgentLens ledger reflected the blocked decision.

## Phase 13: Professional Ledger and Explainability

Make the web surface match the PRD's secondary ledger intent: a professional session
replay and evidence console rather than a toy live dashboard.

Automatic validation:
- Frontend production build passes after adding the UI toolkit dependencies.
- Backend session/policy/risk tests remain green.
- Backend ruff passes.
- Browser smoke confirms the upgraded ledger renders without horizontal overflow.

Human validation:
- Open a local or hosted AgentLens session and confirm the queue, selected gate state,
  inspector, analytics, dependency graph, and Explain More panel are readable.
- Confirm approve/block from Codex proxy still updates the ledger.

Status: implementation complete for the first professional ledger upgrade. The frontend
now uses TanStack Table for the gate queue, Recharts for approval/risk analytics, React
Flow for dependency evidence graphs, and Lucide React for consistent icons. The page was
split into typed helpers and reusable ledger components. Explain More now renders the
existing structured backend response inside the inspector, including trajectory,
confidence factors, dependency evidence, policy match, suggested modification, local
question answering grounded in visible data, and sanitized raw tool payload. Validation
passed: frontend `npm run build`, backend
`UV_CACHE_DIR=.uv-cache env -u AGENTLENS_DISABLE_HOOKS uv run pytest tests/test_session_api.py tests/test_policy_risk.py`
reported 22 passed with 1 warning, backend `./.venv/bin/ruff check .` passed, and a
1440px Playwright smoke rendered the empty-state ledger with no horizontal overflow.

Follow-up status: the ledger now derives analytics from visible gates when the backend
analytics response is still empty for the active timeline, avoiding stale `0 actions`
trust-score displays. The native proxy also mirrors best-effort app-server command/read
telemetry into the ledger for non-approval events when Codex exposes structured payloads.
Approval requests remain the authoritative pre-execution path. Validation passed:
`PYTHONPATH=src env -u AGENTLENS_DISABLE_HOOKS ./.venv/bin/pytest tests/test_codex_proxy.py tests/test_codex_app_server.py`
reported 16 passed, `env -u AGENTLENS_DISABLE_HOOKS ./.venv/bin/pytest -m 'not integration'`
reported 75 passed with 2 integration tests deselected, targeted backend ruff passed, and
frontend `npm run build` passed. With network access allowed,
`env -u AGENTLENS_DISABLE_HOOKS ./.venv/bin/pytest tests/test_openai_integration.py`
reported 2 passed.

Second follow-up status: Console UI layout, sidebar, topbar controls, and metrics boxes have been polished. Sidebar logo alignment is centered in collapsed mode with the close chevron removed. Topbar controls use a fluid flex wrap layout with specific widths to prevent layout overlaps. Metrics boxes use solid bg-white backgrounds with matching border accents and no hover animations. TrajectoryView and AuditEventsView have been reverted from tabbed navigation to responsive side-by-side grids (xl:grid-cols-[1.2fr_0.8fr] and xl:grid-cols-[1.1fr_0.9fr]) showing both sections simultaneously. Production Next.js build compiled successfully.

Third follow-up status: A new "Flow Map" view is added as an alternative supervision
surface alongside the existing Review Queue. It visualizes the session as a connected
React Flow graph (original instruction → traces → gates). The view has been upgraded
to support grouping multiple sequential tasks/prompts executed in the same session
into separate, unconnected flowcharts. Predicted trajectory future steps ("likely next"
nodes) are completely removed from the graph itself to keep the layout clean. Production Next.js `npm run build` passes.

Fourth follow-up status: The Flow Map has been enriched into a fully interactive, dual-pane console. Users can select nodes directly on the flowchart to open detail inspectors for Gates, Traces, and Task prompts in the right column, resolve pending gates with inline Approve/Block/Modify controls, inspect pretty-printed parameters and git diffs in a dark terminal style block, and toggle background grid/interaction options via top bar controls. Production Next.js build passes.

Fifth follow-up status: Refactored Flow Map to use React Flow's native `onNodeClick` and HTML `div` wrappers, resolving a node click event swallowing bug. Optimized the dashboard shell layout by introducing context-aware compact headers, hiding session selection and Slack integrations on global pages, rendering the metrics strip conditionally, and redesigning metrics cards into a 40% shorter inline-flex layout. Production Next.js build and all pytest tests pass.

## Phase 14: Policy Management UI

Make the PRD policy engine manageable from the session ledger instead of only through
manual YAML edits.

Automatic validation:
- Policy config endpoints load, validate, save, and test draft policy rules.
- Backend policy/risk/session API tests remain green.
- Backend ruff passes for touched files.
- Frontend production build passes with the editable policy page.

Human validation:
- Open the Policy Ledger view.
- Create or edit a rule, test it against a sample proposal, save it, reload the page, and
  confirm the rule persists in `agentlens.config.yaml`.
- Run a Codex write prompt and confirm the policy ledger still shows runtime matches.

Status: first implementation complete. The backend exposes `GET /policies`,
`PUT /policies`, and `POST /policies/test`, all backed by the repo's
`agentlens.config.yaml`. Policy saves are normalized YAML writes through a temporary file
replace, and draft policy tests use the same ordered `PolicyEngine` path as live gates.
The frontend Policy Ledger page now includes a rule editor, create/duplicate/delete,
reorder controls, save/reload actions, and a draft simulator for representative tool
calls. Validation passed: frontend `npm run build`, backend
`UV_CACHE_DIR=.uv-cache env -u AGENTLENS_DISABLE_HOOKS uv run pytest tests/test_session_api.py tests/test_policy_risk.py`
reported 25 passed with 1 warning, full backend non-integration validation reported
83 passed with 2 integration tests deselected and 1 warning, targeted backend ruff
passed, and real OpenAI integration tests reported 2 passed with network access.

Follow-up status: Explain More now supports backend-backed gate questions through
`POST /gates/{gate_id}/questions`. Answers are grounded in visible trace metadata,
risk/policy evidence, dependency evidence, git excerpts, and intelligence-card context.
The deterministic fallback is used without OpenAI credentials; OpenAI-backed answers use
cost-aware routing when credentials are configured. The frontend Explain tab now posts
questions to the backend and displays answer evidence plus the model/fallback role.

## Phase 14A: One-Command Local Stack

Reduce local workflow friction by replacing the four-terminal setup with one command that
starts all local AgentLens services and launches Codex through the native proxy.

Automatic validation:
- Unit tests pin the generated Codex command and configured local URLs.
- Backend ruff passes.
- Existing proxy tests remain green.

Human validation:
- Run `cd backend && uv run agentlens-dev --repo /Users/aaryan/Desktop/Agent_Lens`.
- Confirm the local API, frontend, proxy, and Codex TUI start from that single command.
- Confirm `Ctrl+C` stops the stack.
- If the console script is not refreshed, use
  `uv run --no-sync python -m agentlens.dev_stack --repo /Users/aaryan/Desktop/Agent_Lens`.

Status: implementation complete for first local workflow runner. `agentlens-dev` starts
the local guard API, Next.js ledger, Codex proxy, waits for readiness, and launches Codex
with the required native proxy flags. `--no-codex` starts services only and prints the
Codex command. `--open-dashboard` opens the ledger in the default browser once services
are ready. Smoke validation passed on alternate localhost ports with `--no-codex`:
the stack reached ready, printed the Codex command, and shut down cleanly on Ctrl+C.
Focused tests reported 12 passed for `tests/test_dev_stack.py tests/test_codex_proxy.py`,
and backend ruff passed.
