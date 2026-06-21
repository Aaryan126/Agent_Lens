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

Status: in progress. Deployment docs, backend Dockerfile, Render blueprint, configurable CORS,
PostgreSQL URL normalization, and opt-in PostgreSQL-backed runtime storage are implemented.
