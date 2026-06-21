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

Status: complete for backend integration. Block Kit rendering, signature verification,
approve/block/modify/explain handling, and CLI payload preview are implemented. A real
Slack app still needs to be configured for human validation.

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

Status: planned.
