# AgentLens — Product Requirements Document

**Version:** 0.1 — Competition Draft  
**Focus agent:** OpenAI Codex  
**Core thesis:** The value of AgentLens is not the gate. It's the intelligence inside the gate.

---

## 1. The Problem

AI coding agents like Codex are no longer just suggesting code — they are acting. Writing files, calling APIs, modifying schemas, deleting directories. The human who triggered the agent is now a bystander to a process they nominally control but cannot meaningfully supervise.

The existing mental model — "I give the agent a task, I check the output" — breaks down when:

- Actions are irreversible (deleted file, dropped table, sent webhook)
- The agent's inferred goal has silently drifted from the user's actual intent
- The user has no visibility into the agent's reasoning, only its outputs
- Confidence is treated as binary: the agent either acts or it doesn't

There is currently no layer between **"agent decides"** and **"action executes"** that is intelligent enough to be worth having. Existing tools offer either full autonomy (agent runs freely) or crude interruption (approve every single step). Neither is usable at the speed agents operate.

**The core insight:** Humans cannot supervise what they cannot understand at the speed it moves. The problem is not that agents act — it is that humans are asked to make approval decisions with almost no useful information to reason from.

---

## 2. What AgentLens Is

AgentLens is a **judgment layer** — a Python SDK that wraps Codex and intercepts every tool call before execution, enriches it with contextual intelligence, and delivers a decision to the human in the surface they are already in, at the moment it matters, and then disappears.

It is not a dashboard you monitor. It is a system that **reaches you when your judgment is needed** and gives you everything required to exercise that judgment well.

The product has two surfaces:

- **Ambient notifications** — the primary experience. A push to Slack or mobile when a gate is triggered. Decision made in one tap, context fully rendered, then gone.
- **Session ledger** — the secondary experience. A lightweight web view you open occasionally to replay a session, understand patterns, and build trust in the system over time. Not a live operations center.

---

## 3. The Intelligence Layer — Core of the Product

This is what separates AgentLens from a confirm dialog. Each component below represents a distinct technical problem.

### 3.1 Trace Engine

Hooks into Codex at the function-calling layer via OpenAI's tool use API. Every tool invocation — file read, file write, shell command, API call, database query — is captured as a structured event with:

- Tool name and raw parameters
- Codex's internal reasoning chain (the scratchpad/chain-of-thought preceding the call)
- Timestamp and session context
- The state of the working directory at that moment (git diff snapshot)

This trace is the foundation everything else builds on. Without it, all downstream intelligence is guessing.

### 3.2 Semantic Risk Classifier

Not a rules engine. A context-aware classifier that scores each action on two axes:

**Reversibility** — can this be undone?
- High: deleting a file with no git backup, dropping a database table, sending an external webhook, pushing to a remote branch
- Medium: modifying a tracked file, adding a dependency, changing an environment variable
- Low: reading files, running tests, creating new files in a feature branch

**Blast radius** — how many things does this action affect?
- This is where the classifier goes beyond naive rules. It is not enough to know that a file is being deleted. The classifier must understand whether that file is imported by other modules, referenced in a config, or entirely isolated. It computes a dependency graph of the codebase at session start and uses it to score blast radius dynamically.

Example: deleting `utils/temp_cache.py` — low blast radius if nothing imports it, high blast radius if 14 modules depend on it. Same action type, completely different risk profile. A rules engine cannot distinguish these. The semantic classifier can.

The output is a 2×2 risk matrix:

|  | Low blast radius | High blast radius |
|---|---|---|
| **Reversible** | Auto-execute | Review |
| **Irreversible** | Review | Block + alert |

### 3.3 Counterfactual Trajectory Engine

This is the deepest feature and the most novel.

Instead of asking "should I approve this action?", AgentLens asks "if I approve this action, what is Codex likely to do next, and when is the earliest point of no return?"

At each gate, a secondary LLM call takes:
- The current trace
- The action being proposed
- The working codebase state
- The original user instruction

And returns a predicted next-3-steps trajectory with an identified **commitment point** — the step after which undoing the chain becomes meaningfully harder.

This reframes the approval decision entirely. The human is not rubber-stamping one tool call. They are approving or rejecting a direction. That is a fundamentally more useful thing to ask a human to do.

Example output rendered in the approval notification:

> Codex wants to drop the `sessions` table.  
> If approved, likely next steps: (1) regenerate migration file, (2) update ORM models, (3) restart dev server.  
> Point of no return: step 1 — migration file creation is logged and shared with teammates.  
> Confidence in this trajectory: 74%

### 3.4 Goal Drift Detector

Codex is given an instruction. As the session progresses, the agent's behavior can silently diverge from that instruction — solving a related but different problem, over-engineering, or pursuing an inferred sub-goal the user never asked for.

AgentLens continuously compares:
- The original user instruction (embedded at session start)
- The semantic summary of what Codex has actually done so far
- The stated intent of the current proposed action

When cosine similarity between the original instruction embedding and the inferred current goal drops below a configurable threshold, AgentLens surfaces a drift alert — not as a hard block, but as a soft flag in the next approval card:

> Heads up: Codex appears to be rebuilding the entire auth system. Your original instruction was to fix the password reset bug. Still want to continue?

This is proactive oversight. The human does not need to track what the agent is doing — AgentLens does it for them.

### 3.5 Calibrated Confidence Layer

Risk level alone ("High / Medium / Low") is not enough information for a human to make a good decision. AgentLens surfaces the agent's actual confidence in each action, derived from:

- Entropy of the token distribution at the decision point (low entropy = high confidence)
- Whether the action matches patterns seen earlier in the session
- Whether the stated reason matches the codebase evidence

Output is a numeric confidence score attached to every approval card. Users can set per-policy confidence thresholds — for example, auto-approve medium-risk actions only if confidence > 80%, otherwise escalate to human.

This makes the approval gate dynamic rather than purely action-type-based. Codex deleting a file at 94% confidence is a different decision than Codex deleting a file at 51% confidence.

### 3.6 Translation Layer

Every approval card renders the proposed action as one plain-English sentence written for a developer who has not been watching the session:

- Raw: `tool_call: fs.delete(path="/src/db/migrations/0014_sessions.py", reason="identified as redundant")`
- Translated: "Codex wants to permanently delete a database migration file — it believes the file is unused, but 2 other migration files reference it. Confidence: 58%."

The translation call uses a secondary Claude/GPT call with a strict prompt that requires: action summary, stated agent reason, codebase evidence for or against, and confidence. It is constrained to 2 sentences maximum to force clarity.

---

## 4. Interaction Model — Push, Not Pull

### 4.1 Primary Surface: Ambient Decision Card

When a gate triggers, AgentLens pushes a structured notification. The primary channel is Slack; secondary is mobile push via a companion app.

The card contains:
- One-line plain-English summary (from translation layer)
- Risk badge (color-coded: green / amber / red)
- Confidence score ("Codex confidence: 58%")
- Trajectory preview ("If approved, next likely action: regenerate migration")
- Drift flag if active ("Note: this may be outside your original scope")
- Three actions: **Approve** / **Block** / **Explain more**
- Optional: **Modify** (opens a lightweight text input to redirect Codex inline)

The card is designed to be actionable in under 10 seconds without opening any other surface. The human reads it, taps a button, and returns to what they were doing. Codex resumes or halts accordingly.

### 4.2 "Explain More" Flow

If the human taps Explain more, a follow-up card expands with:
- Full reasoning chain from Codex (the raw scratchpad, rendered legibly)
- Dependency graph snippet showing what files are affected
- The counterfactual trajectory in full
- A free-text input to ask AgentLens a question ("why does it think this file is redundant?")

This is a second LLM call that answers the user's question in context, using the full trace as grounding.

### 4.3 Secondary Surface: Session Ledger

A lightweight web view (Next.js) opened optionally at the end of a session or week. Contents:

- **Session timeline:** chronological replay of everything Codex did, every gate triggered, every human decision made
- **Approval patterns:** what types of actions you block most often — surfaces candidates for new standing policies
- **Drift history:** sessions where goal drift was detected and whether the human caught it
- **Trust score:** a per-session metric showing what percentage of Codex actions required human intervention, trending over time as policies improve

The ledger is a tool for building trust and improving policy — not for moment-to-moment supervision.

---

## 5. Policy Engine

Standing rules that remove the human from decisions that don't need them, while ensuring they are always present for the ones that do.

Policies are defined in a `agentlens.config.yaml` file at the repo root and managed via the web UI:

```yaml
policies:
  - name: protect production
    condition: path contains "/prod" or path contains "/migrations"
    action: require_approval
    min_confidence: 0.0  # always escalate regardless of confidence

  - name: api spend cap
    condition: tool == "api_call" and cumulative_spend > 5.00
    action: block_and_alert

  - name: auto-approve safe reads
    condition: tool in ["fs.read", "run_tests", "git.status"]
    action: auto_execute

  - name: low confidence gate
    condition: confidence < 0.75 and risk_level != "low"
    action: require_approval
```

Policies are evaluated in order. The first match wins. All policy evaluations are logged to the audit trail.

---

## 6. Workflow — End to End

```
Developer gives Codex a task
        │
        ▼
AgentLens SDK wraps the Codex session
        │
        ▼
Codex proposes a tool call
        │
        ▼
Trace Engine captures: tool, params, reasoning chain, codebase state
        │
        ▼
Policy Engine evaluates against standing rules
        │
    ┌───┴───┐
    │       │
Auto-execute  Gate triggered
(low risk,    │
policy match) ▼
        Semantic Risk Classifier scores reversibility + blast radius
              │
              ▼
        Counterfactual Trajectory Engine predicts next 3 steps
              │
              ▼
        Goal Drift Detector checks alignment with original instruction
              │
              ▼
        Calibrated Confidence Layer scores agent certainty
              │
              ▼
        Translation Layer renders plain-English summary
              │
              ▼
        Decision card pushed to Slack / mobile
              │
         ┌────┴────┐
         │         │
      Approve    Block / Modify
         │         │
         ▼         ▼
    Action fires  Codex receives
                  rejection + reason,
                  adjusts and continues
              │
              ▼
        All branches → Audit Log (immutable, timestamped)
```

---

## 7. Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| SDK | Python | Matches Codex/OpenAI ecosystem; wraps function-calling hooks natively |
| Backend | FastAPI | Async-first, fast enough for real-time trace processing |
| Intelligence calls | OpenAI GPT-4o | Translation, trajectory, drift detection as secondary LLM calls |
| Embeddings | OpenAI `text-embedding-3-small` | Goal drift detection via cosine similarity |
| Real-time | WebSockets (native FastAPI) | Live trace streaming to ledger |
| Session ledger frontend | Next.js + Tailwind | Lightweight, fast to build |
| Database | PostgreSQL | Audit log — append-only, indexed by session and timestamp |
| Session state | Redis | In-flight trace buffer, policy cache |
| Notifications | Slack API (Block Kit) | Primary decision surface |
| Auth | Clerk | Fast to integrate, handles teams |
| Deployment | Railway or Render | Fast to ship for competition |

---

## 8. Integrations

| Integration | Purpose |
|---|---|
| OpenAI Codex API | Primary agent — all tool calls intercepted here |
| Slack API | Primary decision surface — Block Kit cards with interactive buttons |
| GitHub API | File diff rendering inside approval cards |
| Webhook (outbound) | Custom pipelines, enterprise integration |
| Mobile push (future) | Companion app for approvals away from Slack |

---

## 9. What Makes This Defensible

The moat is not the interception layer — that is a commodity. The moat is:

- **The semantic risk classifier** trained on codebase dependency graphs, not action types
- **The counterfactual trajectory engine** — no existing oversight tool does this
- **The drift detector** — catches misalignment before it compounds
- **The audit corpus** — every session logged makes the classifier smarter over time (network effect on risk scoring)
- **EU AI Act Article 14** — mandates human oversight for high-risk AI systems; AgentLens is the compliance primitive

---

## 10. The One-Liner

AgentLens is not a dashboard you monitor. It is the intelligence layer that reaches you when your judgment is needed — and makes that judgment worth having.
