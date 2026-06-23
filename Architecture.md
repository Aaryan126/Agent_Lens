# AgentLens Architecture

## System Overview

AgentLens is a judgment layer for AI coding agents (primarily OpenAI Codex). It sits between the agent and its execution environment, intercepting proposed tool calls, evaluating them through a pipeline of deterministic risk analysis and LLM-driven intelligence, then deciding whether to auto-execute, gate for human approval, or block outright. All decisions are recorded in an append-only audit ledger.

The system follows a local-first architecture: a Python/FastAPI backend runs as a local guard process, a Next.js/TypeScript frontend provides the session ledger and approval console, and multiple adapter paths let Codex connect through hooks, a WebSocket proxy, or a direct app-server bridge.

---

## High-Level System Diagram

```mermaid
graph TB
    subgraph "User"
        DEV[Developer]
    end

    subgraph "Agent Layer"
        CODEX[Codex CLI / TUI]
    end

    subgraph "AgentLens Backend (Python / FastAPI)"
        API[FastAPI Server port 8787]
        SESSION[AgentLensSession]
        TRACE[TraceEngine]
        RISK[SemanticRiskClassifier]
        POLICY[PolicyEngine]
        INTEL[IntelligenceLayer]
        STORE[Storage Layer]
        AUDIT[Audit Log]
    end

    subgraph "AgentLens Frontend (Next.js)"
        UI[Session Ledger / Approval Console]
    end

    subgraph "External Services"
        OPENAI[OpenAI API]
        PG[(PostgreSQL)]
    end

    DEV -->|gives task| CODEX
    CODEX -->|proposes tool calls| API
    API --> SESSION
    SESSION --> TRACE
    SESSION --> RISK
    SESSION --> POLICY
    SESSION --> INTEL
    INTEL --> OPENAI
    SESSION --> STORE
    STORE --> AUDIT
    STORE --> PG
    API --> UI
    DEV -->|approves / blocks| UI
    UI --> API
```

---

## Connection Paths

```mermaid
graph LR
    subgraph "Codex Connection Modes"
        H1[agentlens-hook<br/>post-process hook]
        H2[agentlens-codex-proxy<br/>WebSocket MITM]
        H3[agentlens-run<br/>app-server stdio]
        H4[agentlens-codex<br/>CLI JSONL mode]
    end

    subgraph "AgentLens Backend"
        API[FastAPI<br/>port 8787]
    end

    subgraph "Frontend"
        UI[Next.js<br/>port 3000]
    end

    H1 -->|HTTP POST| API
    H2 -->|HTTP + WS| API
    H3 -->|HTTP| API
    H4 -->|HTTP| API
    UI -->|HTTP polling| API
```

---

## Core Data Flow

```mermaid
sequenceDiagram
    participant Agent as Codex
    participant AL as AgentLensSession
    participant Trace as TraceEngine
    participant Risk as SemanticRiskClassifier
    participant Policy as PolicyEngine
    participant Intel as IntelligenceLayer
    participant Store as Storage
    participant Human as Developer

    Agent->>AL: propose(tool_call)
    AL->>Trace: capture(proposal, repo_path)
    Trace-->>AL: TraceEvent (with git snapshot)
    AL->>Store: add_trace(event)
    AL->>Risk: assess(proposal)
    Risk->>Risk: compute reversibility
    Risk->>Risk: compute blast radius via DependencyGraph
    Risk-->>AL: RiskAssessment
    AL->>Policy: evaluate(proposal, risk)
    Policy->>Policy: iterate policies, first match wins
    Policy-->>AL: PolicyDecision

    alt Policy = AUTO_EXECUTE
        AL->>Intel: fallback_card()
        Intel-->>AL: IntelligenceCard (deterministic)
        AL->>Store: add_gate(status=AUTO_EXECUTED)
    else Policy = REQUIRE_APPROVAL or BLOCK_AND_ALERT
        AL->>Intel: build_card(context)
        Intel->>Intel: trajectory prediction (OpenAI)
        Intel->>Intel: drift assessment (embeddings)
        Intel->>Intel: confidence calibration
        Intel->>Intel: translation summary (OpenAI)
        Intel-->>AL: IntelligenceCard
        AL->>Store: add_gate(status=PENDING or BLOCKED)
    end

    alt Gate = PENDING
        Store-->>Human: notification (dashboard)
        Human->>Store: approve / block / modify
        Store->>Store: update_gate(status, resolved_at)
    end

    Store-->>Agent: decision response
```

---

## Backend Component Architecture

```mermaid
graph TB
    subgraph "Entry Points"
        GUARD[agentlens-guard<br/>uvicorn server]
        DEMO[agentlens-demo<br/>CLI simulator]
        HOOK[agentlens-hook<br/>Codex post-process]
        PROXY[agentlens-codex-proxy<br/>WebSocket proxy]
        RUN[agentlens-run<br/>app-server terminal]
        CODEX_CLI[agentlens-codex<br/>JSONL mirror]
        DEV_STACK[agentlens-dev<br/>full stack orchestrator]
    end

    subgraph "Core Session"
        SESSION[AgentLensSession]
    end

    subgraph "Pipeline"
        TRACE[TraceEngine]
        RISK[SemanticRiskClassifier]
        RISK_SUB[DependencyGraph<br/>AST + regex import scanning]
        POLICY[PolicyEngine]
        INTEL[IntelligenceLayer]
        ROUTER[ModelRouter]
    end

    subgraph "Storage"
        MEM[InMemoryStore]
        DB_STORE[DatabaseBackedStore]
        PG_REPO[SqlAlchemyLedgerRepository]
        AUDIT_LOG[JsonlAuditLog / DatabaseAuditLog]
    end

    subgraph "External"
        OPENAI_API[OpenAI API]
        PG[(PostgreSQL)]
    end

    GUARD -->|HTTP| SESSION
    DEMO --> SESSION
    HOOK -->|HTTP| API
    PROXY -->|HTTP| API
    RUN -->|HTTP| API
    CODEX_CLI -->|HTTP| API
    DEV_STACK -->|subprocess| GUARD

    SESSION --> TRACE
    SESSION --> RISK
    RISK --> RISK_SUB
    SESSION --> POLICY
    SESSION --> INTEL
    INTEL --> ROUTER
    INTEL --> OPENAI_API

    SESSION --> MEM
    MEM --> AUDIT_LOG
    MEM --> DB_STORE
    DB_STORE --> PG_REPO
    PG_REPO --> PG
    DB_STORE --> AUDIT_LOG
```

---

## Intelligence Pipeline

```mermaid
flowchart LR
    A[DecisionContext] --> B{OpenAI key?}
    B -->|No| C[FallbackCard<br/>deterministic only]
    B -->|Yes| D[ModelRouter<br/>chooses STRONG vs NANO]
    D --> E[TrajectoryPrediction<br/>OpenAI responses.parse]
    D --> F[DriftAssessment<br/>embedding cosine similarity<br/>threshold: 0.62]
    D --> G[ConfidenceCalibration<br/>base + adjustment factors]
    E --> H[Translation<br/>nano model, 2-sentence summary]
    F --> H
    G --> H
    H --> I[IntelligenceCard]
    C --> I
```

### Model Routing Logic

| Condition | Model Role |
|-----------|-----------|
| Policy action is not `auto_execute` | STRONG |
| Risk level is MEDIUM, HIGH, or CRITICAL | STRONG |
| Tool is `fs.write`, `fs.delete`, `api.call`, `db.query` | STRONG |
| Tool is `shell.run` | STRONG |
| All other cases | NANO |

For summaries: HIGH/CRITICAL risk uses STRONG, everything else uses NANO.

---

## Risk Classification

```mermaid
flowchart TB
    P[ToolCallProposal] --> R{Reversibility}
    P --> B{Blast Radius}

    R -->|fs.read / git.status / run_tests| RL[LOW]
    R -->|shell.run + read-only command| RL
    R -->|fs.delete / destructive DB / curl/deploy| RH[HIGH]
    R -->|everything else| RM[MEDIUM]

    B -->|read-only actions| BL[LOW]
    B -->|/prod / /migrations / deploy| BH[HIGH]
    B -->|dependency >= 5 files| BH
    B -->|dependency 1-4 files / API/DB/shell| BM[MEDIUM]
    B -->|no evidence| BL

    RL & BL --> AUTO[AUTO_EXECUTE]
    RH & BH --> BLOCK[BLOCK_AND_ALERT]
    RM & BL --> APPROVE[REQUIRE_APPROVAL]
    RL & BM --> APPROVE
    RL & BH --> APPROVE
    RM & BM --> APPROVE
    RM & BH --> APPROVE
    RH & BM --> APPROVE
    RH & BL --> APPROVE
```

The blast radius computation uses `DependencyGraph`, which parses Python imports via AST and JavaScript/TypeScript imports via regex to build a map of which files import which modules. Config references (package.json, pyproject.toml, Dockerfile, README, etc.) are also scanned.

---

## Policy Evaluation Pipeline

```mermaid
flowchart TB
    P[ToolCallProposal + RiskAssessment] --> E{iterate policies<br/>in config order}

    E -->|first match| MATCH{condition type}

    MATCH -->|tool_in| T{proposal.tool_name in list?}
    MATCH -->|path_contains| PATH{param values contain fragment?}
    MATCH -->|param_contains| PARAM{named param contains fragment?}
    MATCH -->|confidence_below| CONF{proposal.confidence < threshold?}
    MATCH -->|risk_not| RISK{risk_level != value?}

    T -->|yes| USE[use policy action]
    PATH -->|yes| USE
    PARAM -->|yes| USE
    CONF -->|yes| USE
    RISK -->|yes| USE

    T -->|no| NEXT[next policy]
    PATH -->|no| NEXT
    PARAM -->|no| NEXT
    CONF -->|no| NEXT
    RISK -->|no| NEXT

    E -->|no match| FALLBACK{risk exists?}

    FALLBACK -->|yes| RISK_ACTION[use risk.recommended_action]
    FALLBACK -->|no| DEFAULT[REQUIRE_APPROVAL]

    USE --> ACTIONS{PolicyAction}
    ACTIONS -->|auto_execute| AUTO[AUTO_EXECUTED]
    ACTIONS -->|block_and_alert| BLOCKED[BLOCKED]
    ACTIONS -->|require_approval| PENDING[PENDING]

    RISK_ACTION --> ACTIONS
    DEFAULT --> PENDING
```

---

## Storage Layer

```mermaid
classDiagram
    class InMemoryStore {
        +dict sessions
        +list traces
        +dict gates
        +AuditLog audit_log
        +add_session()
        +add_trace()
        +add_gate()
        +update_gate()
        +pending_gates()
        +timeline()
    }

    class DatabaseBackedStore {
        +SqlAlchemyLedgerRepository repository
        +reload()
        +add_session()
        +add_trace()
        +add_gate()
        +update_gate()
    }

    class SqlAlchemyLedgerRepository {
        +create_schema()
        +add_session()
        +add_trace()
        +upsert_gate()
        +list_sessions()
        +list_traces()
        +list_gates()
    }

    class AuditLog {
        <<abstract>>
        +append()
        +read_all()
    }

    class JsonlAuditLog {
        +append()
        +read_all()
    }

    class DatabaseAuditLog {
        +append()
        +read_all()
    }

    InMemoryStore <|-- DatabaseBackedStore
    InMemoryStore --> AuditLog
    DatabaseBackedStore --> SqlAlchemyLedgerRepository
    JsonlAuditLog --|> AuditLog
    DatabaseAuditLog --|> AuditLog
    DatabaseAuditLog --> SqlAlchemyLedgerRepository

    PostgreSQL --> SqlAlchemyLedgerRepository
```

Storage is selected at startup based on `AGENTLENS_STORAGE_BACKEND`:
- `memory` (default): `InMemoryStore` with `JsonlAuditLog` writing to `local_data/agentlens_audit.jsonl`.
- `postgres`: `DatabaseBackedStore` which mirrors in-memory operations to PostgreSQL via `SqlAlchemyLedgerRepository`.

---

## Data Models

```mermaid
erDiagram
    Session ||--o{ TraceEvent : has
    Session ||--o{ Gate : has
    TraceEvent ||--o{ Gate : results-in

    Session {
        string id PK
        string original_instruction
        string repo_path
        string user_id
        string team_id
        string config_path
        datetime created_at
    }

    TraceEvent {
        string id PK
        string session_id FK
        string proposal_id
        string tool_name
        dict params
        string stated_reason
        GitSnapshot git_snapshot
        datetime created_at
    }

    Gate {
        string id PK
        string session_id FK
        string proposal_id FK
        GateStatus status
        PolicyDecision policy_decision
        RiskAssessment risk_assessment
        IntelligenceCard intelligence_card
        string human_reason
        string modified_instruction
        datetime created_at
        datetime resolved_at
    }

    AuditEvent {
        int id PK
        string event_type
        datetime created_at
        dict payload
    }
```

---

## API Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/sessions` | Create a new session |
| GET | `/sessions` | List sessions |
| GET | `/sessions/latest` | Get most recent session |
| GET | `/sessions/{id}/timeline` | Get traces + gates |
| GET | `/sessions/{id}/analytics` | Trust score, patterns, distributions |
| POST | `/sessions/{id}/tool-calls` | Submit a proposal, get a Gate |
| GET | `/gates/pending` | All pending gates |
| GET | `/gates/{id}` | Single gate |
| POST | `/gates/{id}/approve` | Approve |
| POST | `/gates/{id}/block` | Block |
| POST | `/gates/{id}/modify` | Modify with instruction |
| POST | `/gates/{id}/observe` | Mark auto-executed |
| POST | `/gates/{id}/explain` | Full explanation |
| POST | `/gates/{id}/questions` | Natural language Q&A |
| GET | `/policies` | Read policy config |
| PUT | `/policies` | Save policy config |
| POST | `/policies/test` | Test draft policies |
| GET | `/audit/events` | Recent audit events |

---

## Frontend Component Tree

```mermaid
graph TB
    subgraph "Next.js Single Page App (port 3000)"
        HOME[Home (page.tsx)]
        SHELL[AppShell]
        METRICS[MetricsStrip]

        subgraph "Views"
            REVIEW[ReviewLedger]
            FLOW[FlowMapView]
            TRAJ[TrajectoryView]
            POL[PolicyLedgerView]
            SLACK[SlackSurfaceView]
            AUDIT[AuditEventsView]
        end

        subgraph "Review Sub-components"
            GATE_TABLE[GateTable<br/>TanStack Table]
            INSPECTOR[GateInspector]
            TIMELINE[TimelineAnalyticsTabs]
            EXPLAIN[ExplainMorePanel]
            DEP_GRAPH[DependencyGraph<br/>React Flow mini-graph]
        end
    end

    subgraph "Libraries"
        TANSTACK[@tanstack/react-table]
        XYFLOW[@xyflow/react]
        RECHARTS[recharts]
        LUCIDE[lucide-react]
        TAILWIND[Tailwind CSS]
    end

    HOME --> SHELL
    SHELL --> METRICS
    HOME --> REVIEW
    HOME --> FLOW
    HOME --> TRAJ
    HOME --> POL
    HOME --> SLACK
    HOME --> AUDIT

    REVIEW --> GATE_TABLE
    REVIEW --> INSPECTOR
    REVIEW --> TIMELINE
    INSPECTOR --> EXPLAIN
    INSPECTOR --> DEP_GRAPH

    GATE_TABLE --> TANSTACK
    FLOW --> XYFLOW
    DEP_GRAPH --> XYFLOW
    TIMELINE --> RECHARTS
    SHELL --> LUCIDE
```

The frontend is a single-page Next.js 15 app with six client-side views toggled by a state variable. All state lives in the root `Home` component and is props-drilled to children.

### Frontend Views

| View | Component | Purpose |
|------|-----------|---------|
| review | `ReviewLedger` | Gate queue (TanStack Table) + Inspector with explain/trajectory/dependency views |
| flow | `FlowMapView` | React Flow directed graph of the session timeline |
| trajectory | `TrajectoryView` | Counterfactual trajectory cards per gate |
| policies | `PolicyLedgerView` | CRUD policy rules, test drafts, save to config |
| slack | `SlackSurfaceView` | Send pending gates to Slack channel |
| audit | `AuditEventsView` | Full session replay + analytics charts |

---

## Entry Points

| CLI Command | Module | Function | How It Works |
|-------------|--------|----------|-------------|
| `agentlens-guard` | `guard.py` | Starts FastAPI on port 8787 | Local-first API server. All other entry points talk to this via HTTP. |
| `agentlens-demo` | `cli.py` | Creates session with fixture/default proposals | CLI simulator for testing without Codex. |
| `agentlens-hook` | `codex_hook.py` | Codex post-processing hook | Reads JSON from stdin, creates/updates sessions, posts proposals, polls for decisions, exits 2 if blocked. |
| `agentlens-codex` | `codex_terminal.py` | Runs Codex CLI in JSONL mode | Mirrors parsed Codex events into AgentLens API, prints readable terminal output. |
| `agentlens-run` | `app_server_terminal.py` | Interactive/prompt mode via app-server | Spawns `codex app-server --stdio`, handles JSON-RPC approval callbacks, waits for human decisions. |
| `agentlens-codex-proxy` | `codex_proxy.py` | WebSocket MITM proxy | Sits between Codex TUI and app-server, intercepts approval requests, enriches with AgentLens intelligence. |
| `agentlens-dev` | `dev_stack.py` | One-command full stack | Spawns guard + frontend + proxy as subprocesses, optionally launches Codex. |

---

## Adapter Architecture

```mermaid
sequenceDiagram
    participant TUI as Codex TUI
    participant Proxy as agentlens-codex-proxy
    participant API as AgentLens API
    participant AS as Codex App-Server

    TUI->>Proxy: WebSocket connect
    Proxy->>AS: WebSocket connect (upstream)

    TUI->>Proxy: thread/start
    Proxy->>AS: thread/start (enriched)
    AS-->>Proxy: thread/start response

    TUI->>Proxy: turn/start
    Proxy->>AS: turn/start (enriched)

    loop Each event
        TUI->>Proxy: event (command, file change, etc.)
        Proxy->>AS: forward event
        alt requestApproval received
            AS-->>Proxy: requestApproval
            Proxy->>API: POST /sessions/{id}/tool-calls
            API-->>Proxy: Gate
            alt Gate = AUTO_EXECUTED
                Proxy->>AS: approve(accept)
            else Gate = BLOCKED
                Proxy->>AS: approve(cancel)
            else Gate = PENDING
                Proxy->>TUI: native approval prompt + AgentLens enrichment
                TUI-->>Proxy: user decision
                Proxy->>API: approve|block gate
                Proxy->>AS: accept|cancel
            end
        else passive telemetry
            Proxy->>API: POST proposal (passive flag)
        end
    end
```

---

## Deployment Architecture

```mermaid
graph TB
    subgraph "Local Development"
        LOCAL_BE[agentlens-guard<br/>FastAPI :8787]
        LOCAL_FE[npm run dev<br/>Next.js :3000]
        LOCAL_DB[(JSONL file)]
    end

    subgraph "Render (Hosted Demo)"
        RENDER_API[Docker<br/>FastAPI]
        RENDER_PG[(PostgreSQL<br/>Render Managed)]
        RENDER_FE[Vercel<br/>Next.js]
    end

    RENDER_API --> RENDER_PG
    RENDER_FE -->|NEXT_PUBLIC_AGENTLENS_API_URL| RENDER_API
    LOCAL_BE --> LOCAL_DB
    LOCAL_FE --> LOCAL_BE
```

The default storage backend is in-memory with JSONL audit logging. PostgreSQL is used in hosted mode on Render. The frontend connects to the backend via the `NEXT_PUBLIC_AGENTLENS_API_URL` environment variable, overridable via a `?api=` query parameter.

---

## Key Design Decisions

1. **Local-first**: The guard runs as a local process on port 8787, keeping all data on the developer's machine by default. Hosted mode with PostgreSQL is available for demos and remote review.

2. **Append-only audit**: Every session start, trace capture, gate creation, and gate update is written to an append-only JSONL audit log (or PostgreSQL in hosted mode). The audit log cannot be modified retroactively -- only new events can be appended.

3. **Cost-aware model routing**: Strong models (gpt-4.1) are only called for consequential actions. Low-risk read-only actions use nano models or deterministic fallback. This keeps operational costs proportional to risk.

4. **Deterministic fallback**: When OpenAI credentials are not configured, the intelligence layer produces deterministic summaries from tool metadata and risk evidence. No LLM calls are required for the system to function.

5. **Thread-safe storage**: `InMemoryStore` uses `RLock` for thread safety. The `DatabaseBackedStore` mirrors to PostgreSQL using `run_blocking()` to bridge sync FastAPI handlers with async SQLAlchemy.

6. **Policy-first evaluation**: Policies are evaluated before intelligence calls. If a policy auto-executes an action, no LLM intelligence is generated -- only a lightweight deterministic card is created.

7. **No WebSockets in the frontend**: The frontend polls REST endpoints on intervals rather than using WebSockets. This simplifies the architecture and avoids connection management complexity for a local-first tool.

8. **Passive observation mode**: Codex hooks can run in mirror-only mode (`passive=true`), recording tool calls for dashboard visibility without blocking execution. This is the default for normal Codex TUI sessions.
