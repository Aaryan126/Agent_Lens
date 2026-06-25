# Agent Lens System Context

Last updated: June 23, 2026

## 1. Product Thesis

Agent Lens is a judgment layer for AI coding agents, with OpenAI Codex as the focus integration. The product does not exist to add another approval dialog. It exists to make human supervision meaningful when coding agents act quickly, repeatedly, and sometimes irreversibly.

The core value is intelligence inside the gate:

- Semantic risk: what can go wrong, how reversible it is, and how large the blast radius is.
- Counterfactual trajectory: what the agent is likely to do next if this action is allowed.
- Goal drift: whether the current action still matches the original user instruction.
- Calibrated confidence: how certain the system is, and why.
- Translation: concise, developer-readable summaries that preserve technical accuracy without forcing the human to parse raw tool payloads.
- Review episodes: human-facing groupings of raw traces/gates so repeated inspections and passive telemetry do not overwhelm the user.

The guiding product assumption is: humans cannot supervise what they cannot understand at the speed it moves. Agent Lens therefore treats raw tool events as audit material, not as the main user experience.

## 2. Current State

The system is now a local-first Agent Lens implementation with hosted-demo support. The most reliable strict-control path is the Codex app-server based flow. Normal Codex TUI hooks still exist, but they are observability-first because native hooks proved unreliable for hard pre-execution blocking in live validation.

Implemented capabilities:

- FastAPI backend with typed Pydantic schemas.
- Local session creation and timeline APIs.
- Trace capture with git status/diff snapshots.
- Deterministic policy and semantic risk evaluation.
- OpenAI-backed trajectory, drift, confidence, translation, and gate Q&A when credentials are configured.
- Cost-aware model routing.
- Local approval, block, modify, explain, observe, and gate question endpoints.
- Slack Block Kit cards and Slack interactivity.
- PostgreSQL-ready runtime storage for hosted demos.
- Local guard API.
- Codex CLI mirroring.
- Guarded app-server terminal.
- Native Codex TUI app-server proxy.
- One-command local dev stack.
- Professional Next.js ledger UI with review queue, flow map, trajectory, policy management, Slack surface, audit replay, and analytics.
- Backend-owned review episode layer for collapsing repeated tool events into human-facing action units.

Current validation status from implementation notes:

- Backend non-integration suite passed after the review episode layer: `90 passed, 2 deselected`.
- Focused session/policy tests passed after the episode layer: `29 passed`.
- Backend ruff passed.
- Frontend `npm run build` passed.
- Real OpenAI integration tests have passed in prior validation when network and `OPENAI_API_KEY` were available.

## 3. Repository Layout

Important paths:

- `prd.md`: product requirements and intended product shape.
- `plan.md`: phased implementation plan and status.
- `implementation.md`: running implementation log and validation history.
- `README.md`: setup and usage guide.
- `backend/`: Python package, FastAPI service, Codex integrations, storage, tests.
- `frontend/`: Next.js operator console / session ledger.
- `docs/`: deeper operational and deployment documentation.
- `examples/`: sample sessions and demo fixtures.
- `.codex/hooks.json`: project-local Codex hook configuration for observability-first TUI mirroring.
- `agentlens.config.yaml`: repo policy config managed by the dashboard.

## 4. Conceptual Model

Agent Lens has two layers of truth:

1. Raw ledger truth
   - Sessions
   - Tool call proposals
   - Trace events
   - Gates
   - Audit events

2. Human-facing intelligence
   - Risk assessment
   - Policy decision
   - Intelligence card
   - Explain More response
   - Gate Q&A
   - Review episodes
   - Analytics

Raw records preserve auditability. Human-facing records compress, translate, and explain raw records so the user can make decisions quickly.

## 5. Main Backend Data Types

The core public boundary lives in `backend/src/agentlens/schemas.py`.

### Session

A session represents one user instruction or one grouped Codex conversation.

Key fields:

- `id`
- `original_instruction`
- `repo_path`
- `user_id`
- `team_id`
- `config_path`
- `created_at`

The original instruction is central to drift detection, episode grouping, and user-facing replay.

### ToolCallProposal

The internal normalized form of an agent action.

Key fields:

- `session_id`
- `tool_name`
- `params`
- `stated_reason`
- `confidence`
- `provider_metadata`
- `created_at`

Supported tool names include:

- `fs.read`
- `fs.write`
- `fs.delete`
- `shell.run`
- `api.call`
- `db.query`
- `git.status`
- `run_tests`

Codex adapters normalize app-server, CLI, hook, and passive telemetry events into this schema.

### TraceEvent

The audit record captured from a proposal.

Key fields:

- `session_id`
- `proposal_id`
- `tool_name`
- `params`
- `stated_reason`
- `provider_metadata`
- `git_snapshot`
- `created_at`

Trace events store visible tool metadata and repository state. They do not store or render hidden chain-of-thought.

### RiskAssessment

Semantic risk result.

Key fields:

- `reversibility`
- `blast_radius`
- `risk_level`
- `recommended_action`
- `evidence`
- `affected_files`

Risk is based on both action type and codebase context.

### PolicyDecision

Ordered policy result.

Key fields:

- `action`
- `matched_policy`
- `reason`

Policy action can be:

- `auto_execute`
- `require_approval`
- `block_and_alert`

### Gate

The approval record for a proposal.

Key fields:

- `session_id`
- `proposal_id`
- `status`
- `policy_decision`
- `risk_assessment`
- `intelligence_card`
- `human_reason`
- `modified_instruction`
- `created_at`
- `resolved_at`

Gate status can be:

- `pending`
- `approved`
- `blocked`
- `modified`
- `auto_executed`

Important distinction: passive telemetry can still produce a gate-shaped record because the system uses one normalized ledger shape, but the review episode layer now distinguishes actionable decisions from already-executed observations.

### IntelligenceCard

The main per-gate intelligence payload.

Key fields:

- `summary`
- `risk_badge`
- `confidence`
- `trajectory_preview`
- `drift_flag`
- `full_trajectory`
- `confidence_evidence`
- `dependency_evidence`
- `drift_score`
- `model_roles`

If OpenAI is not configured, deterministic fallback cards are generated. Fallback summaries now describe concrete target and intent instead of leading with raw tool names.

### ReviewEpisode

The backend-owned human-facing grouping layer.

Key fields:

- `id`
- `session_id`
- `prompt`
- `kind`
- `status`
- `risk_level`
- `confidence`
- `primary_gate_id`
- `trace_ids`
- `gate_ids`
- `descriptor`
- `summary`
- `counts`
- `created_at`
- `updated_at`

Episode kinds currently include:

- `inspection_batch`: repeated context-gathering reads/searches.
- `decision`: actionable review unit with a primary gate.
- `observation_batch`: already-executed passive telemetry.

Episodes are computed from raw traces/gates at timeline read time. They are not currently stored as independent database rows.

### ActionDescriptor

The user-facing translation object attached to an episode.

Key fields:

- `human_title`
- `plain_action`
- `target_label`
- `technical_detail`
- `raw_detail`
- `evidence_summary`

This descriptor prevents raw shell fragments such as `2>/dev/null` from becoming the primary UI target. Those details remain available as raw detail.

## 6. End-to-End Flow

High-level flow:

```text
User gives Codex a task
        |
        v
Codex proposes or emits an action
        |
        v
Adapter normalizes it into ToolCallProposal
        |
        v
TraceEngine captures TraceEvent and git snapshot
        |
        v
SemanticRiskClassifier scores risk
        |
        v
PolicyEngine applies ordered repo policies
        |
        v
IntelligenceLayer builds card or deterministic fallback
        |
        v
Gate is created/resolved
        |
        v
Timeline API computes ReviewEpisode records
        |
        v
Frontend renders episode-first ledger and gate inspector
```

For strict app-server flows, Codex waits for an accept/cancel response when a pending action is routed through Agent Lens. For passive telemetry, the event is recorded as observed and auto-executed because it already happened.

## 7. Trace Capture

Trace capture is implemented in `backend/src/agentlens/trace.py`.

For every proposal, the trace engine captures:

- Tool name
- Params
- Stated reason
- Provider metadata
- Git status
- Git diff snapshot

Git snapshots are truncated to keep payloads usable. If the repo path is unavailable or git fails, the snapshot records an error instead of blocking the session.

Trace capture is intentionally narrow. It records visible tool metadata and code evidence, not hidden reasoning.

## 8. Semantic Risk

Risk classification is implemented in `backend/src/agentlens/risk.py`.

Risk has two main axes:

- Reversibility
- Blast radius

Reversibility examples:

- Low: file reads, git status, tests, read-only shell commands.
- Medium: file writes or shell commands that may mutate local state.
- High: deletes, destructive DB queries, external webhooks, deploys, pushes, `rm -rf`.

Blast radius examples:

- Low: no broad references or external state.
- Medium: imported/referenced code, database/API calls, local mutating shell actions.
- High: production, migrations, deployment, destructive DB operations, broad dependency impact.

The classifier builds a lightweight dependency graph:

- Python imports
- JavaScript/TypeScript imports
- Config/doc references
- Shell command path references

Read-only shell/file inspections are short-circuited to low risk before dependency blast-radius checks. This prevents repo overview tasks from becoming pending gates just because they inspect important files.

Known limitation: semantic risk is deterministic and conservative. It is useful as a baseline, but not a substitute for deeper static analysis or complete language-aware dependency resolution.

## 9. Policy Engine

Policies are loaded from `agentlens.config.yaml` and managed through the Policy Ledger UI.

Policy endpoints:

- `GET /policies`
- `PUT /policies`
- `POST /policies/test`

Policy matching supports:

- `tool_in`
- `path_contains`
- `param_contains`
- `confidence_below`
- `risk_not`

`path_contains` handles real Codex app-server target shapes, including:

- `params.path`
- `params.paths`
- file keys
- grant roots
- command/query text
- raw provider target fields
- visible stated reason

Policies are evaluated in order. First match wins. If no policy matches, semantic risk recommendation drives the decision.

## 10. Intelligence Layer

Implemented in `backend/src/agentlens/intelligence.py`.

The intelligence layer builds a typed `DecisionContext` with:

- Original instruction
- Current proposal
- Risk assessment
- Policy decision
- Recent traces
- Recent gates
- Git snapshot
- Dependency evidence
- Inferred session goal
- Visible metadata

When OpenAI credentials are configured, the system can generate:

- Structured trajectory prediction
- Embedding-based drift assessment
- Calibrated confidence
- Translation summary
- Gate-specific Q&A answers

When OpenAI is not configured, deterministic fallbacks keep the system usable.

Model routing:

- Strong model for consequential gated intelligence.
- Nano/lightweight model for low-risk summaries and question answers.
- Embedding model for drift.

OpenAI calls are behind typed ports and structured Pydantic outputs where applicable.

## 11. Review Episodes

The review episode layer is implemented in `backend/src/agentlens/episodes.py`.

It solves a core UX problem: raw Codex tool streams can contain many repeated steps for small tasks. For example, changing one sentence in `architecture.md` may produce many shell/file events, several repeated permission callbacks, and passive app-server telemetry. Rendering all of that as rows or graph nodes makes the system less intelligent than a raw log.

Episodes are built by grouping raw records by:

- Prompt
- Target
- Action family
- Actionability
- Timeline order

Action families include:

- inspect
- edit
- delete
- command
- file action
- external/tool-specific fallback

Primary gate selection prefers:

1. Pending gates.
2. Higher-risk gates.
3. Earlier gate order within the group.

The episode layer outputs:

- One human title.
- One target label.
- One summary.
- Linked raw trace ids.
- Linked gate ids.
- Primary gate id for approval actions.
- Counts for raw traces/gates.

Important behavior:

- Repeated inspections collapse into `inspection_batch`.
- Passive already-executed telemetry becomes `observation_batch`.
- Actionable approval requests become `decision`.
- Shell redirection fragments such as `2>/dev/null` are never selected as target labels.
- Raw details remain accessible for audit evidence.

Current limitation: episodes are computed dynamically from current traces/gates and are not persisted as immutable objects. That is acceptable for current local and hosted demo usage because raw records are still the source of truth.

## 12. Backend API Surface

Main session APIs:

- `POST /sessions`
- `GET /sessions`
- `GET /sessions/latest`
- `GET /sessions/{session_id}/timeline`
- `GET /sessions/{session_id}/analytics`
- `POST /sessions/{session_id}/tool-calls`

Gate APIs:

- `GET /gates/pending`
- `GET /gates/{gate_id}`
- `POST /gates/{gate_id}/approve`
- `POST /gates/{gate_id}/block`
- `POST /gates/{gate_id}/modify`
- `POST /gates/{gate_id}/observe`
- `POST /gates/{gate_id}/explain`
- `POST /gates/{gate_id}/questions`

Policy APIs:

- `GET /policies`
- `PUT /policies`
- `POST /policies/test`

Slack APIs:

- `POST /demo/slack/send`
- `POST /integrations/slack/actions`

Codex/local APIs:

- `POST /codex/sessions`

Audit APIs:

- `GET /audit/events`

Health:

- `GET /health`

## 13. Storage and Audit

Storage lives in `backend/src/agentlens/storage.py`.

Runtime storage supports:

- In-memory local store.
- JSONL-backed local history through `AGENTLENS_STORAGE_BACKEND=local_jsonl` and `AGENTLENS_AUDIT_LOG_PATH`.
- PostgreSQL-backed store through `AGENTLENS_STORAGE_BACKEND=postgres`.

Database support is implemented in `backend/src/agentlens/db.py` using SQLAlchemy-ready ledger repositories.

Stored entities:

- Sessions
- Traces
- Gates
- Audit events

Review episodes are currently computed from stored traces/gates and are not persisted.
For local development, the default guard/dev-stack path replays
`local_data/agentlens_audit.jsonl` into runtime state on startup. That repo-local file is
ignored by git, and it keeps previous Codex sessions available in the dashboard session
picker after restart.

Audit model:

- `session_started`
- `trace_captured`
- `gate_created`
- `gate_updated`

The audit log is append-oriented. Gate updates write a new audit event with the latest gate payload.

## 14. Codex Integration Surfaces

Agent Lens has several Codex integration paths. They exist because Codex surfaces expose different levels of control.

### Simulator / Demo

The initial path uses demo fixtures and `agentlens-demo` to generate predictable sessions and Slack payloads.

Use for:

- Local UI smoke tests.
- Hosted demo validation.
- Competition-style demos.

### Codex CLI Adapter

The CLI adapter parses `codex exec --json` output into proposals.

Use for:

- Terminal-first mirroring.
- Read-only or preview style sessions.
- Hosted forwarding demos.

Limitation:

- It mirrors parsed proposals. It is not the strictest live approval loop.

### Project-local Hooks

Configured in `.codex/hooks.json`.

Hooks mirror:

- `UserPromptSubmit`
- `PreToolUse`
- `PermissionRequest`

Current mode:

- Observability-first by default.
- `AGENTLENS_ENFORCE_APPROVALS=0` is used because live validation showed hook timeouts could occur while Codex still applied edits.

Use for:

- Passive visibility into normal Codex sessions.
- Not for reliable hard blocking.

### Guarded App-Server Terminal

Command:

```bash
cd backend
uv run agentlens-run --repo /path/to/repo
```

This launches Codex through app-server JSON-RPC, owns the approval callback path, creates Agent Lens gates, waits for decisions, and sends accept/cancel responses back to Codex.

Use for:

- Strictest local approval loop.
- Terminal-native decisions with `approve`, `block`, or `modify`.
- Gate-specific dashboard URLs.

### Native Codex TUI App-Server Proxy

Commands:

```bash
cd backend
uv run agentlens-guard --repo /path/to/repo
uv run agentlens-codex-proxy --repo /path/to/repo
AGENTLENS_DISABLE_HOOKS=1 codex --ask-for-approval untrusted --sandbox workspace-write --remote ws://127.0.0.1:8791
```

The proxy sits between the native Codex TUI and Codex app-server.

It:

- Creates/continues Agent Lens sessions from `turn/start`.
- Intercepts app-server approval requests.
- Posts proposals to Agent Lens.
- Auto-accepts auto-executed/approved/modified gates.
- Cancels blocked gates.
- Forwards pending gates to the native Codex approval prompt with Agent Lens context.
- Records native Codex approve/cancel decisions back into Agent Lens.
- Mirrors passive app-server telemetry when structured events are available.
- Uses target hints from prompts and passive telemetry to improve file-change approval targeting.

Use for:

- Normal Codex TUI experience with Agent Lens oversight.
- Preferred experimental native TUI integration path.

## 15. Frontend Ledger

The frontend is a Next.js app in `frontend/app`.

Main files:

- `page.tsx`: state orchestration, API polling, session selection, decision calls.
- `types.ts`: frontend API types.
- `utils.ts`: formatting, fallback episodes, local API helpers.
- `components/ledger-ui.tsx`: review queue, inspector, analytics, policy ledger, audit, shared panels.
- `components/flow-map-view.tsx`: React Flow map and node inspectors.

Major views:

- Review Queue
- Flow Map
- Trajectory
- Policy Ledger
- Slack Surface
- Audit Events

### Review Queue

Primary supervision surface in the dashboard.

Current behavior:

- Renders `ReviewEpisode` records first.
- Shows actionable `decision` episodes as rows.
- Shows collapsed inspection batches.
- Selects the primary gate for decisions.
- Keeps approve/block/modify operating on gates.

### Inspector

The right-side inspector renders:

- Summary
- Risk
- Blast radius
- Confidence
- Policy match
- Trajectory
- Dependency graph
- Confidence factors
- Risk evidence
- Decision history
- Explain More
- Gate Q&A
- Raw sanitized tool payload

### Flow Map

Flow Map now renders semantic episode nodes instead of every trace/gate node.

It shows:

- Task start
- Inspection batches
- Decision episodes
- Observation batches
- Task completion

Selecting a decision episode opens the primary gate inspector. Selecting an inspection/observation episode opens an episode inspector with summary, evidence, raw details, and raw record counts.

### Audit Events

Audit Events now defaults to narrative replay through episodes.

It shows:

- Episode label
- Episode kind
- Human title
- Summary
- Raw trace/gate counts

Raw trace/gate records remain available through linked ids and inspector panels rather than being the first thing a human sees.

### Trajectory

Trajectory view filters to meaningful decision episodes. This avoids showing repeated passive/inspection callbacks as predicted-direction entries.

### Policy Ledger

Policy Ledger lets users:

- Load policies from `agentlens.config.yaml`.
- Create/edit/delete/duplicate/reorder rules.
- Save normalized YAML.
- Test draft policies against sample proposals.
- Review runtime matches.

## 16. Analytics and Trust

Analytics live in `backend/src/agentlens/analytics.py`.

Current analytics include:

- Trust score
- Auto-executed count
- Human intervention count
- Total actions
- Approval patterns
- Risk distribution
- Drift history

Frontend has fallback analytics from visible gates when backend analytics returns empty for a non-empty timeline.

Known limitation: analytics are still gate-count based. The episode layer improves UI comprehension, but deeper analytics should eventually distinguish:

- Raw trace count
- Passive observation count
- Actionable decision count
- Human intervention count by episode
- Auto-executed action count by episode

## 17. Slack Surface

Slack support lives in `backend/src/agentlens/slack.py`.

Implemented:

- Block Kit rendering.
- Request signature verification.
- Interactive action parsing.
- Approve/block/modify/explain handling.
- Slack Web API posting for demo cards.
- Message update after resolution.

Slack currently operates around gates, not review episodes. The richer episode layer is available in timeline APIs, but full Slack episode cards are a natural follow-up.

## 18. Explain More and Gate Q&A

Explain endpoint:

- `POST /gates/{gate_id}/explain`

Returns:

- Summary
- Risk
- Policy
- Trajectory
- Drift flag
- Confidence
- Confidence evidence
- Dependency evidence
- Suggested modification
- Context summary

Question endpoint:

- `POST /gates/{gate_id}/questions`

Answers are grounded in:

- Visible trace metadata
- Risk/policy evidence
- Dependency evidence
- Git excerpts
- Intelligence-card context

Without OpenAI credentials, deterministic fallback answers are returned. With OpenAI credentials, cost-aware summary routing is used.

## 19. Local Development Commands

Install backend dependencies:

```bash
cd backend
uv sync --extra dev
```

Run backend tests:

```bash
cd backend
uv run pytest
```

Run backend non-integration tests:

```bash
cd backend
env -u AGENTLENS_DISABLE_HOOKS uv run pytest -m 'not integration'
```

Run real OpenAI tests when credentials are configured:

```bash
cd backend
uv run pytest -m integration
```

Run backend ruff:

```bash
cd backend
./.venv/bin/ruff check .
```

Run local guard:

```bash
cd backend
uv run agentlens-guard --repo /path/to/repo
```

Run frontend:

```bash
cd frontend
NEXT_PUBLIC_AGENTLENS_API_URL=http://127.0.0.1:8787 npm run dev
```

Build frontend:

```bash
cd frontend
npm run build
```

Start one-command local stack:

```bash
cd backend
uv run agentlens-dev --repo /path/to/repo
```

Start stack without launching Codex:

```bash
cd backend
uv run agentlens-dev --repo /path/to/repo --no-codex
```

## 20. Environment Variables

Common variables:

- `OPENAI_API_KEY`: enables OpenAI-backed intelligence and integration tests.
- `OPENAI_MODEL`: strong model for consequential intelligence.
- `OPENAI_NANO_MODEL`: lightweight model for summaries.
- `OPENAI_EMBEDDING_MODEL`: embedding model for drift.
- `AGENTLENS_STORAGE_BACKEND`: `memory` for ephemeral tests, `local_jsonl` for repo-local history, or `postgres` for hosted durable state.
- `DATABASE_URL`: PostgreSQL URL for hosted/runtime persistence.
- `AGENTLENS_AUDIT_LOG_PATH`: JSONL audit log path.
- `AGENTLENS_DISABLE_HOOKS`: disables older project hooks when using proxy flow.
- `AGENTLENS_ENFORCE_APPROVALS`: hook mode enforcement toggle; currently off by default for normal TUI hooks.
- `AGENTLENS_APPROVAL_TIMEOUT_SECONDS`: hook/app approval wait tuning.
- `NEXT_PUBLIC_AGENTLENS_API_URL`: frontend API target.
- Slack variables for bot token, signing secret, and channel id.

Never commit `.env`, local databases, caches, logs, or generated test artifacts.

## 21. Current Strengths

Strong areas:

- Product architecture is aligned with the PRD: intelligence is centered, not raw confirmation.
- Local-first workflow keeps repository context on the developer machine.
- App-server paths provide practical strict control.
- Native TUI proxy preserves Codex user experience while adding Agent Lens oversight.
- Risk/policy/intelligence layers are typed and testable.
- UI now presents review episodes rather than raw repeated callbacks.
- Explain/Q&A surfaces are grounded in visible evidence.
- Policy management is usable from the dashboard.
- Hosted demo path remains available.

## 22. Known Gaps and Cautions

Important limitations:

- Normal Codex project hooks are not a reliable hard-control path. They are observability-first unless running through the app-server-controlled paths.
- Review episodes are computed, not persisted. Raw records remain the source of truth.
- Slack still centers gate cards, not full episode cards.
- Analytics are still mostly gate-count based rather than episode-count based.
- Semantic risk is deterministic and partial; it is not a full static analyzer.
- Dependency graph coverage is useful but incomplete for complex repos, dynamic imports, generated code, and non-Python/JS ecosystems.
- OpenAI intelligence depends on credentials, network availability, and model behavior. Deterministic fallback must remain correct and useful.
- Git snapshots are truncated.
- Hidden chain-of-thought is intentionally not stored or rendered.
- Hosted free-tier infrastructure may sleep, restart, or expire depending on provider limits.

## 23. Recommended Next Work

Highest-leverage follow-ups:

1. Make Slack cards episode-aware so ambient notifications match the improved ledger.
2. Update analytics to report both raw actions and decision episodes.
3. Persist review episodes if immutable episode history becomes important.
4. Add an explicit raw log expansion UI for each episode.
5. Add visual regression tests for the small-document-edit scenario that originally exposed repetition.
6. Improve risk evidence for shell commands with redirection and command wrappers.
7. Add richer target extraction for app-server file-change payloads across more Codex versions.
8. Add policy suggestions based on repeated user decisions.
9. Build a compact "10 second approval card" view for each episode.
10. Continue hardening the native app-server proxy as the preferred production-grade Codex integration.

## 24. Mental Model for Future Contributors

When adding features, preserve these boundaries:

- Raw records are for audit.
- Episodes are for human comprehension.
- Gates are for decisions.
- Policies are deterministic and ordered.
- Risk is deterministic baseline judgment.
- OpenAI intelligence enriches, but must not be required for core safety.
- Codex app-server paths are control paths.
- Hooks are observability paths.
- The dashboard is a secondary ledger, not the primary work surface.
- Slack/native Codex prompts are the interruption surfaces.

The product should avoid asking users to approve every mechanical step. Instead, it should ask for judgment at meaningful moments and provide enough context for a developer who has not been watching the session to understand what is happening.
