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
- Live validation confirmed read-only Codex repo inspection now collapses into an auto-executed inspection batch. A normal TUI README edit still executed before a dashboard approval decision, so TUI hook enforcement is now documented as best-effort and tool/event dependent. The inspector now hides decision controls for resolved gates and auto-selects pending gates when they appear.
- A guarded app-server terminal path is now implemented through `agentlens-run`. It launches
  Codex app-server over JSON-RPC, starts a Codex thread/turn, creates an AgentLens session,
  streams readable events to the terminal, maps app-server command/file-change/permission
  approval requests into AgentLens proposals, waits for pending gate decisions, and returns
  accept/cancel responses back to Codex. This is the intended strict local control path;
  project hooks remain useful for observing normal TUI sessions but are not the hard-control
  surface for every edit path.
- Focused validation passed for the new guarded terminal path:
  `uv run pytest tests/test_codex_app_server.py tests/test_codex_adapter.py tests/test_session_api.py`
  reported 20 passed.
- Full local validation also passed after the app-server addition: `uv run pytest`
  reported 60 passed, `uv run ruff check .` passed, frontend `npm run build` passed,
  and `uv run agentlens-run --help` loaded the new console script successfully.
- Live `agentlens-run` validation then confirmed the app-server approval path works:
  a read-only repo summary completed with auto-executed shell approvals, and a README edit
  produced a pending `fs.write` gate while Codex waited in the terminal. The frontend had
  a session-switching bug where opening a new `?session=...` link could leave the queue on
  an older session while analytics reflected the new session; `refreshSession` now replaces
  the active session and persists the matching local API/session IDs. The inspector copy was
  also updated to distinguish strict app-server decisions from best-effort TUI hook decisions.
- A second live validation pass exposed an interaction between app-server sessions and normal
  project hooks: local `/sessions/latest` polling could switch the dashboard from an explicit
  `agentlens-run` session to a newer hook-created session, causing approvals to be applied to
  the wrong gates while the app-server CLI kept polling the original pending gate. Explicit
  `?session=...` links are now pinned, so latest-session polling cannot steal focus from the
  active app-server session. Frontend `npm run build` passed after the fix.
- Multi-terminal session management is implemented for the local console. `GET /sessions`
  returns recent sessions, and the frontend header includes a session picker plus an explicit
  Follow Latest control. This lets users keep multiple Codex terminals open while deliberately
  choosing which AgentLens session receives approvals. Validation passed:
  `uv run pytest tests/test_session_api.py` reported 12 passed and frontend `npm run build`
  passed.
- App-server approval prompts now print gate-specific dashboard URLs containing `session`,
  `api`, and `gate` query parameters. The frontend honors `?gate=...` by selecting that
  exact gate while preserving the pinned session, reducing approval ambiguity when several
  Codex terminals or hook-created sessions are active at the same time.
- `agentlens-run` now supports terminal-native gate decisions. When an app-server action is
  pending, the terminal accepts `a`/`approve`, `b`/`block`, or `m`/`modify` while continuing
  to poll the dashboard for remote decisions. The dashboard session lock is now persisted in
  localStorage, so returning to another Codex terminal cannot silently move a pinned review
  URL back to `/sessions/latest`; users must click Follow Latest to opt back into that mode.
- A first native Codex TUI proxy is implemented through `agentlens-codex-proxy`. It starts a
  local `codex app-server`, exposes `ws://127.0.0.1:8791` for `codex --remote`, intercepts
  app-server approval requests, creates AgentLens gates, auto-accepts low-risk resolved
  gates, forwards pending gates to the native Codex approval prompt with an AgentLens summary
  and dashboard link, and records native approve/cancel responses back into the AgentLens
  ledger.
- Focused proxy validation passed: `./.venv/bin/pytest tests/test_codex_proxy.py
  tests/test_codex_app_server.py` reported 9 passed, and `./.venv/bin/ruff check .` passed.
- Live normal Codex TUI testing showed project hooks are not a reliable hard-control path:
  `PreToolUse` and `PermissionRequest` timed out after 30 seconds while Codex still applied a
  README edit. Hook-originated proposals now use deterministic fast cards instead of full
  OpenAI intelligence, `.codex/hooks.json` sets `AGENTLENS_ENFORCE_APPROVALS=0`, and the
  proxy instructions use `AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted --sandbox workspace-write --remote ...` so hooks do not
  compete with app-server approval control.
- The proxy prompt copy now matches that workflow directly: startup instructions print the
  `AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted --sandbox workspace-write --remote ...` command, and native Codex approval
  reasons render concise AgentLens review copy from the proposal target, risk level, and
  first evidence item while keeping the dashboard URL only in `agentLens.dashboardUrl`
  metadata.
- The proxy now preflights `GET /health` on the AgentLens API before accepting Codex TUI
  connections. If `agentlens-guard` is not running, it fails fast with the exact local guard
  command instead of crashing during `turn/start`.
- The Codex TUI proxy now rewrites forwarded `thread/start` and `turn/start` messages to
  enforce the proxy's approval policy and sandbox settings while preserving a user approvals
  reviewer. Native approval reasons render as a single readable line with double-space
  separators, and dashboard URLs remain only in `agentLens` metadata. Validation passed:
  `./.venv/bin/pytest tests/test_codex_proxy.py` reported 9 passed and
  `./.venv/bin/ruff check .` passed.
- The documented native proxy command now includes Codex's explicit approval and sandbox
  flags: `AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted --sandbox workspace-write --remote ws://127.0.0.1:8791`.
  The proxy startup copy prints the same shape using its configured approval policy and
  sandbox. Validation passed: `./.venv/bin/pytest tests/test_codex_proxy.py
  tests/test_codex_app_server.py` reported 14 passed, and `./.venv/bin/ruff check .`
  passed.
- The native proxy now applies sandbox settings with Codex's method-specific app-server
  schema. `thread/start` receives the sticky `sandbox` mode, while follow-up `turn/start`
  messages receive a structured `sandboxPolicy` object and no legacy `sandbox` field. This
  fixes the second-prompt `turn/start failed in TUI` failure seen during `agentlens-dev`
  testing. Validation passed: `PYTHONPATH=src env -u AGENTLENS_DISABLE_HOOKS
  ./.venv/bin/pytest tests/test_codex_proxy.py tests/test_codex_app_server.py
  tests/test_dev_stack.py` reported 19 passed, and `./.venv/bin/ruff check
  src/agentlens/codex_proxy.py tests/test_codex_proxy.py tests/test_dev_stack.py` passed.
  Full backend non-integration validation also passed:
  `PYTHONPATH=src env -u AGENTLENS_DISABLE_HOOKS ./.venv/bin/pytest -m 'not integration'`
  reported 76 passed, 2 deselected, with 1 Starlette/httpx deprecation warning.
- Phase 12 human validation passed for the native Codex TUI proxy approve path. The local
  guard ran on `127.0.0.1:8787`, the frontend connected to the local guard, and
  `agentlens-codex-proxy` ran on `ws://127.0.0.1:8791`. Codex was launched with
  `AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted --sandbox workspace-write --remote ws://127.0.0.1:8791`.
  A read-only prompt produced auto-executed AgentLens ledger entries. A README edit prompt
  triggered the native Codex permission prompt with AgentLens reason copy, and approving in
  Codex allowed the README edit.
- Final automated validation passed after clearing the live proxy
  `AGENTLENS_DISABLE_HOOKS=1` environment for hook unit tests:
  `env -u AGENTLENS_DISABLE_HOOKS uv run pytest` reported 73 passed with 1 warning,
  `env -u AGENTLENS_DISABLE_HOOKS uv run pytest tests/test_codex_proxy.py tests/test_codex_app_server.py`
  reported 14 passed, `./.venv/bin/ruff check .` passed, and frontend
  `npm run build` passed.
- Phase 13 professional ledger upgrade is implemented for the frontend. The monolithic
  page was split into typed helpers and reusable ledger components, with TanStack Table
  powering the decision queue, Recharts powering approval/risk analytics, React Flow
  rendering dependency evidence graphs, and Lucide React providing consistent iconography.
  The inspector now exposes a richer Explain More panel backed by `POST /gates/{gate_id}/explain`,
  deterministic local gate-question answers, confidence calibration, dependency evidence,
  policy match, trajectory, and sanitized raw tool payload.
- Phase 13 validation passed: frontend `npm run build` passed, backend
  `UV_CACHE_DIR=.uv-cache env -u AGENTLENS_DISABLE_HOOKS uv run pytest tests/test_session_api.py tests/test_policy_risk.py`
  reported 22 passed with 1 warning, backend `./.venv/bin/ruff check .` passed, and a
  Playwright browser smoke at 1440px rendered the upgraded ledger with no horizontal
  overflow. The Playwright run required escalated browser permissions on macOS; backend
  404 console errors were expected because no local session existed during the empty-state
  screenshot.
- A one-command local stack runner is implemented as `agentlens-dev`. It starts the local
  guard API, Next.js ledger frontend, native Codex app-server proxy, waits for readiness,
  and launches Codex with `AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted
  --sandbox workspace-write --remote ws://127.0.0.1:8791`. `--no-codex` starts only the
  services and prints the Codex command. A module fallback is documented for existing
  environments before the console script is refreshed:
  `uv run --no-sync python -m agentlens.dev_stack --repo ...`. `--open-dashboard` can
  open the ledger in the default browser after services are ready.
- Local stack smoke passed on alternate ports with `--no-codex`: the guard, frontend, and
  proxy all reached ready, printed the Codex connection command, and shut down cleanly on
  Ctrl+C. Focused validation passed with `PYTHONPATH=src env -u AGENTLENS_DISABLE_HOOKS
  ./.venv/bin/pytest tests/test_dev_stack.py tests/test_codex_proxy.py` reporting 12
  passed, and backend `./.venv/bin/ruff check .` passed.
- The native proxy now mirrors best-effort non-approval app-server command/read telemetry
  into AgentLens when Codex emits structured events, so read-only exploration can enrich
  the ledger even when no approval prompt is required. Duplicate passive events are
  suppressed by method/tool/target or item id, and failures are ignored so Codex TUI
  streaming is not disrupted.
- The frontend ledger now derives analytics from visible gates when the backend analytics
  response is empty for a non-empty timeline. This prevents stale `0 actions` trust-score
  displays while polling local proxy sessions.
- Validation passed after the passive telemetry and analytics fallback changes:
  `PYTHONPATH=src env -u AGENTLENS_DISABLE_HOOKS ./.venv/bin/pytest tests/test_codex_proxy.py tests/test_codex_app_server.py`
  reported 16 passed, `env -u AGENTLENS_DISABLE_HOOKS ./.venv/bin/pytest -m 'not integration'`
  reported 75 passed with 2 integration tests deselected, targeted backend `ruff check`
  passed for the touched proxy/adapter files, and frontend `npm run build` passed. With
  network access allowed, `env -u AGENTLENS_DISABLE_HOOKS ./.venv/bin/pytest
  tests/test_openai_integration.py` reported 2 passed.
- Native proxy sessions now group follow-up prompts from the same Codex remote TUI thread
  into one AgentLens session instead of creating a new dashboard session per prompt. The
  proxy resets the AgentLens session only when Codex starts a new thread. It also resolves
  older outstanding native approval gates with the same native accept/cancel decision so
  stale command gates do not remain pending after Codex continues, and command approval
  payload parsing now recursively extracts nested command/cwd fields. The dashboard no
  longer restores a persistent localStorage session lock on normal page load; it follows
  latest by default unless the current page is explicitly pinned through a URL or manual
  session selection. Validation passed: proxy/app-server/dev-stack tests reported 23
  passed, targeted backend ruff passed, frontend `npm run build` passed, and full backend
  non-integration tests reported 80 passed with 2 integration tests deselected and 1
  existing Starlette/httpx deprecation warning.

## Known Gaps

- Slack backend integration is implemented and live-validated through ngrok.
- PostgreSQL runtime storage is implemented and live-validated against Render Postgres.
- Redis remains a documented future target for in-flight state/cache, but it is not required for the hosted demo path yet.
- Codex hook payload shapes have been hardened against the observed local flow, but normal TUI edit/apply_patch enforcement is not yet guaranteed before execution.
- Project-local hooks are now intentionally observability-first by default. They should not be
  presented as the strict approval mechanism for writes.
- Deep attachment to an arbitrary already-running Codex TUI is still not promised. The strict
  path is now `agentlens-run`, which owns the app-server approval channel. Normal TUI hook
  attachment remains best-effort observability unless future Codex APIs expose stable
  attachment to an existing interactive thread.
- Permission-profile approval requests in app-server mode are mapped conservatively and still
  need live validation with network/MCP/escalated-permission payloads.
- Native Codex TUI proxy enrichment is validated for concise reason-copy display in the
  standard native permission prompt. A full first-class AgentLens card inside Codex may
  still require an upstream Codex extension point or a maintained fork.
- Native proxy approve and block/cancel behavior has been live-validated for README edit
  prompts, but broader permission classes still need hardening.
- Native proxy passive telemetry depends on the structured event payloads Codex app-server
  emits. Approval requests are deterministic; non-approval "Explored" UI items may still
  be absent from the ledger if Codex does not expose enough event detail.

## Next Steps

1. Warm `https://agentlens-api-ggkh.onrender.com/health` before judging because Render free web services sleep after idle.
2. Renew or upgrade Render Postgres before July 21, 2026 if the demo must remain live.
3. Live-test `agentlens-run` with a read-only inspection task, a small README write, and a blocked risky action while the dashboard is open.
4. Live-test two simultaneous `agentlens-run` terminals and confirm the session picker/pinned URLs route approvals to the intended terminal.
5. Capture app-server permission-profile, MCP, and network approval payloads and harden the permission response mapping.
6. Add read/test policy management UI on top of `agentlens.config.yaml`.
7. Keep project hooks as passive/local-TUI observability and use `agentlens-run` whenever strict pre-execution gating is required.
8. Review the frontend npm audit finding before forcing dependency changes; the available audit fix is breaking.
