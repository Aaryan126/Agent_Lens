# AgentLens Live Validation Guide

Use this guide after the local demo passes. These steps validate the remaining external-service
pieces: live Slack buttons and PostgreSQL-backed storage readiness.

## 1. Local Baseline

Run this first:

```bash
./scripts/competition_demo.sh
```

Expected:

- Backend tests pass.
- Backend lint passes.
- Frontend build passes.
- Local CLI demo emits safe, medium-risk, and critical-risk gates.
- Slack Block Kit preview emits valid payload JSON.

## 2. Slack Live Button Validation

### A. Start AgentLens

Terminal 1:

```bash
cd backend
uv run uvicorn agentlens.api:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Confirm:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

### B. Expose the Backend

Use one of these.

Option 1, ngrok:

```bash
ngrok http 8000
```

Option 2, Cloudflare Tunnel:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Copy the HTTPS URL. The Slack Interactivity URL will be:

```text
https://YOUR_PUBLIC_URL/integrations/slack/actions
```

### C. Create or Configure Slack App

In Slack API dashboard:

1. Go to `https://api.slack.com/apps`.
2. Create an app or open the existing AgentLens app.
3. Go to **Interactivity & Shortcuts**.
4. Turn **Interactivity** on.
5. Set **Request URL** to:

```text
https://YOUR_PUBLIC_URL/integrations/slack/actions
```

6. Save changes.
7. Go to **Basic Information**.
8. Copy **Signing Secret**.
9. Put it in `.env`:

```bash
SLACK_SIGNING_SECRET=your_real_signing_secret
```

10. Restart the backend server after editing `.env`.

### D. Validate Slack Signature Locally

Run:

```bash
cd backend
uv run pytest tests/test_slack.py
```

Expected:

- All Slack tests pass.

### E. Preview a Card

Run:

```bash
cd backend
uv run agentlens-demo --fixture ../examples/demo_session.json --slack
```

Expected:

- Output includes Block Kit JSON with button action IDs:
  - `approve_gate`
  - `block_gate`
  - `modify_gate`
  - `explain_gate`

### F. Live Slack Button Test

To send a real AgentLens card into Slack, the app needs a bot token and a channel.

1. In Slack app settings, go to **OAuth & Permissions**.
2. Add bot token scopes:

```text
chat:write
```

3. Install or reinstall the app to your workspace.
4. Copy the **Bot User OAuth Token**. It starts with `xoxb-`.
5. Put it in `.env`:

```bash
SLACK_BOT_TOKEN=xoxb-your-token
```

6. Find a channel ID:
   - Open Slack in a browser.
   - Open the target channel.
   - Copy the `C...` channel ID from the URL, or use channel details.

7. Invite the bot to the channel:

```text
/invite @YourSlackAppName
```

8. Restart the backend.

9. Send demo cards from the running backend:

```bash
curl -X POST http://127.0.0.1:8000/demo/slack/send \
  -H "Content-Type: application/json" \
  -d '{"channel_id":"C0123456789"}'
```

Expected:

- The response includes a `session_id`.
- The response includes two posted Slack messages.
- Slack receives pending AgentLens cards.
- Clicking Approve / Block / Modify sends a request through ngrok.
- Backend logs show `POST /integrations/slack/actions`.
- The Slack message is replaced with the updated gate status.

The CLI can still post payloads for preview or manual API checks, but its gates live in
the CLI process and are not available to the running FastAPI server:

```bash
cd backend
uv run agentlens-demo --fixture ../examples/demo_session.json --slack-send-channel C0123456789
```

Report back:

- The public tunnel URL.
- Whether Slack accepted the Request URL.
- Whether `agentlens-demo --slack-send-channel ...` posted a message.
- Whether clicking a button returns a 200 response in the tunnel/backend logs.
- Any Slack error text if it fails.

## 3. PostgreSQL Readiness Validation

The SQLAlchemy models exist, but runtime API state still uses in-memory storage plus JSONL audit.
Use this to validate the schema layer before full runtime migration.

### A. Start Postgres with Docker

```bash
docker run --name agentlens-postgres \
  -e POSTGRES_USER=agentlens \
  -e POSTGRES_PASSWORD=agentlens \
  -e POSTGRES_DB=agentlens \
  -p 5432:5432 \
  -d postgres:16
```

Update `.env` if needed:

```bash
DATABASE_URL=postgresql+asyncpg://agentlens:agentlens@localhost:5432/agentlens
```

### B. Validate DB Model Tests

```bash
cd backend
uv run pytest tests/test_db.py
```

Expected:

- DB metadata tests pass.

### C. Remaining DB Work

The next implementation step is to wire FastAPI runtime reads/writes to the SQLAlchemy repository:

- sessions -> `agentlens_sessions`
- traces -> `agentlens_traces`
- gates -> `agentlens_gates`
- audit events -> `agentlens_audit_events`

Keep JSONL audit enabled as an export/fallback.

## 4. What To Send Back

For Slack:

```text
Tunnel URL:
Slack Request URL accepted? yes/no
Bot token added? yes/no
Channel ID:
Message posted? yes/no
Backend log after button click:
Slack error, if any:
```

For PostgreSQL:

```text
Docker Postgres started? yes/no
DATABASE_URL:
test_db.py result:
Any error output:
```
