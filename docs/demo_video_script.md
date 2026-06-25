# Agent Lens Demo Video Script

Target length: 2:45 to 2:55  
Format: screen recording first, ElevenLabs voiceover added after  
Goal: YC-style product demo that makes the problem obvious, shows the product working, and proves the intelligence layer is the real value.

## Core Message

AI coding agents are moving from suggestions to actions. Agent Lens is the judgment layer between an agent's intent and execution: it captures proposed tool calls, scores semantic risk, predicts what the agent is likely to do next, detects goal drift, explains the action in plain English, and records the whole session in an auditable ledger.

The demo should feel like: "This is the missing control plane for agentic coding."

## Recording Prep

Use a clean desktop, 1440px or wider. Hide bookmarks, notifications, and unrelated terminals. Record without microphone audio, then add the ElevenLabs voiceover.

Recommended reliable recording path:

```bash
cd backend
uv run agentlens-dev --repo /Users/aaryan/Desktop/Agent_Lens --no-codex
```

Open the printed dashboard URL, or open:

```text
http://localhost:3000?api=http%3A%2F%2F127.0.0.1%3A8787
```

Create a deterministic demo session:

```bash
curl -X POST http://127.0.0.1:8787/demo/session
```

The frontend should attach to the latest local session automatically. If it does not, click **Follow Latest** or pick the newest session from the session selector.

Optional live Codex proof insert:

```bash
cd backend
uv run agentlens-run --repo /Users/aaryan/Desktop/Agent_Lens "Make one small wording improvement in README.md. Do not edit any other file."
```

Only use the live insert if it produces a clean pending gate quickly. The main video should not depend on live Codex unpredictability.

## Screen Layout

Use one browser window for the Agent Lens dashboard. Keep a terminal ready off-screen for the optional live insert. Browser zoom should be 90% or 100%, whichever keeps the Review Queue, inspector, and sidebar visible without horizontal scrolling.

Suggested tabs/views to have ready:

- **Review Queue**
- **Trajectory**
- **Flow Map**
- **Policy Ledger**
- **Audit Events**
- **Slack Surface**

## Timeline Script

### 0:00-0:12 - Cold Open: The Problem

On screen:
- Start on the Agent Lens Review Queue with the three demo actions visible.
- Slowly move the cursor over the auto-executed read, the pending write, and the critical delete.

Voiceover:
> AI coding agents are no longer just suggesting code. They run commands, edit files, change migrations, and sometimes delete things. The problem is that the human is still asked a yes-or-no question with almost no context: approve or block.

### 0:12-0:27 - What Agent Lens Is

On screen:
- Keep the Review Queue visible.
- Highlight the sidebar status: backend online, primary surface Codex Native TUI, Slack Ready.
- Select the pending write action.

Voiceover:
> Agent Lens is a judgment layer for coding agents. It sits between Codex and execution, intercepts proposed tool calls, evaluates them with repo and session context, and only interrupts the developer when judgment is actually needed.

### 0:27-0:50 - Show the Gate

On screen:
- In the inspector, show the selected pending `fs.write` action.
- Pause on the summary, risk badge, confidence, policy match, and decision buttons.
- Do not click yet.

Voiceover:
> This is not a generic confirmation dialog. Agent Lens translates the raw tool call into a developer-readable decision: what Codex wants to do, why it thinks the action is safe, how confident the system is, which policy matched, and whether this should auto-run, require review, or be blocked.

### 0:50-1:22 - Risk, Trajectory, Decision

On screen:
- Select the migration delete gate.
- Click the inspector **Evidence** tab for a few seconds.
- Click the inspector **Trajectory** tab.
- Return to the inspector summary and click **Block**. Wait for the status to update.

Voiceover:
> This is the core loop. Agent Lens sees that Codex wants to delete a migration file, scores the action as risky, shows the evidence behind that score, then predicts the likely next steps if I approve it. Instead of approving a single command in isolation, I am deciding whether the agent should continue down this path. In this case, I block it.

### 1:22-1:55 - Flow Map: Live Agent Events

On screen:
- Click **Flow Map** in the sidebar.
- Show the grouped inspection batch, the risky decision node, and the resolved blocked node.
- If using the deterministic demo, say this is a replay of captured agent events.
- If using the optional live Codex insert, keep the Flow Map open while a new action arrives, then let the queue/graph update.

Voiceover:
> The Flow Map is the session in motion. Agent Lens keeps the raw trace for audit, but groups noisy reads and searches into review episodes so the human sees the shape of the agent's work, not a wall of tool calls. In a live Codex run, new events appear here as the agent explores, proposes edits, and waits for review.

### 1:55-2:14 - Ledger and Trust

On screen:
- Click **Audit Events** for 4 seconds.
- Click **Policy Ledger** for 4 seconds.
- Return to **Review Queue** or analytics area.

Voiceover:
> Every decision becomes part of an auditable ledger: what the agent proposed, what policy matched, what evidence Agent Lens used, and what the human decided. That gives teams a feedback loop. Over time, they can see approval patterns, drift history, risk distribution, and which policies should be automated.

### 2:14-2:36 - Local Control and Replay

On screen:
- Preferred live proof: show a terminal running `agentlens-run` or the Codex proxy, then show the dashboard receiving the pending action.
- Reliable fallback: stay in the dashboard and move through **Flow Map**, **Policy Ledger**, and **Audit Events** quickly.
- End this section on **Audit Events** or **Review Queue** so the viewer sees that the decision is recorded, not just displayed.

Voiceover:
> The important part is that this runs locally around the developer's actual agent workflow. Codex can keep working in the terminal, while Agent Lens turns the session into a control plane: live review when an action is risky, policy when a rule is clear, and replay when the team needs to understand what happened.

### 2:36-2:55 - Holistic Close

On screen:
- Return to **Review Queue** with the resolved gate visible.
- Briefly show the selected gate's summary/evidence in the inspector.
- Hold still for the final sentence.

Voiceover:
> The product is not another dashboard and it is not another approve button. Agent Lens is the judgment layer that makes agentic coding governable: semantic risk before execution, trajectory before commitment, human decisions only when they matter, and an audit trail after the work is done. That is how teams get the speed of Codex without giving up control.

## Optional Live Codex Insert

Use this only if the app-server path behaves cleanly during rehearsal. The cleanest place is the **2:14-2:36** slot. If it works, show live events arriving in the Review Queue or Flow Map. If it does not, keep the deterministic dashboard replay and use the control-plane close above.

On screen:
- Show terminal running `agentlens-run`.
- Show Codex waiting on a pending Agent Lens gate.
- Open the printed dashboard URL or show the already attached dashboard session.

Voiceover replacement:
> This is a real local Codex run. Codex is still the work surface, but Agent Lens owns the approval channel. When Codex proposes a risky file change, the terminal waits while the same gate appears in the dashboard with full context.

## ElevenLabs Voiceover Notes

Use a calm, founder-demo delivery. Pace target: 145 to 155 words per minute. Keep emphasis on these phrases:

- "not a generic confirmation dialog"
- "semantic, not just rule-based"
- "what direction is Codex likely to take next"
- "auditable session ledger"
- "intelligence inside the gate"

Avoid sounding like a tutorial. The video should feel like a product argument backed by a working demo.

## Capture Checklist

Before recording:

- Backend health shows online.
- Dashboard is connected to `127.0.0.1:8787`.
- New demo session is selected.
- At least one pending gate is visible.
- One low-risk auto-executed action is visible.
- Migration delete gate is visible or selectable.
- Browser window has no horizontal overflow.
- Terminal, if shown, contains no secrets or irrelevant local paths beyond the repo path.

During recording:

- Move the cursor slowly and deliberately.
- Pause on each key surface for at least 3 seconds.
- Do not scroll rapidly.
- Do not show setup commands in the main cut unless using the optional live insert.
- If Slack credentials are not configured, do not click **Send To Slack**; show the surface only.

## Backup Plan

If the local dev stack is unstable, use the simpler API/frontend path:

```bash
cd backend
uv run uvicorn agentlens.api:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm run dev
```

Then create the fixture session:

```bash
curl -X POST http://127.0.0.1:8000/demo/session
```

Open:

```text
http://localhost:3000?api=http%3A%2F%2F127.0.0.1%3A8000
```

This still shows the core product: safe auto-execution, gated writes, critical delete review, trajectory, evidence, decisions, policy, Slack surface, and audit ledger.
