# Agent Lens Hosted Demo Deployment

The judging demo should use stable public URLs instead of local ngrok. The recommended
split is:

- Backend API: Render web service with managed PostgreSQL.
- Frontend UI: Vercel Next.js deployment.
- Slack Interactivity Request URL: the Render backend URL.

Free-tier caveats to plan around:

- Render free web services spin down after 15 minutes without inbound traffic and can take
  about a minute to wake up. Warm the backend with `/health` before judging.
- Render free Postgres expires 30 days after creation. Create the database close to demo
  day or upgrade if the demo needs to live longer.
- Vercel Hobby is free for personal, non-commercial projects and is suitable for this
  judging demo frontend.

## 1. Backend on Render

Use the included `render.yaml` blueprint or create the service manually.

Required backend settings:

```text
AGENTLENS_STORAGE_BACKEND=postgres
DATABASE_URL=<Render Postgres connection string>
OPENAI_API_KEY=<real key>
OPENAI_MODEL=gpt-4.1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
SLACK_BOT_TOKEN=<xoxb token>
SLACK_SIGNING_SECRET=<Slack signing secret>
SLACK_CHANNEL_ID=<demo channel ID>
AGENTLENS_CORS_ORIGINS=<Vercel frontend URL>
```

Current hosted demo values:

```text
Backend: https://agentlens-api-ggkh.onrender.com
Frontend: https://frontend-ashy-mu-csvn2wfbmk.vercel.app
Postgres: agentlens-db / dpg-d8rtkbe7r5hc73epfmpg-a
Postgres expiry: 2026-07-21
```

Notes:

- Render may provide `DATABASE_URL` as `postgres://...` or `postgresql://...`; Agent Lens
  normalizes that to the async SQLAlchemy driver automatically.
- `AGENTLENS_STORAGE_BACKEND=postgres` is required for durable hosted state. Without it,
  the app uses in-memory state and Slack buttons can break after a restart.
- The current hosted backend is configured with `AGENTLENS_STORAGE_BACKEND=postgres` and
  has been validated after a Render service restart.
- After deployment, verify:

```bash
curl https://YOUR_RENDER_SERVICE.onrender.com/health
```

Expected:

```json
{"status":"ok"}
```

## 2. Frontend on Vercel

Deploy the `frontend/` directory.

Set this Vercel environment variable:

```text
NEXT_PUBLIC_AGENTLENS_API_URL=https://YOUR_RENDER_SERVICE.onrender.com
```

Then redeploy the frontend. The public Vercel URL is the judging link for the UI.

## 3. Slack Production URL

In Slack app settings, replace the ngrok Request URL:

```text
https://YOUR_RENDER_SERVICE.onrender.com/integrations/slack/actions
```

Then save the Slack app settings.

If the bot token or scopes changed:

1. Go to **OAuth & Permissions**.
2. Confirm `chat:write` exists under bot token scopes.
3. Reinstall the app to the workspace.
4. Confirm `SLACK_BOT_TOKEN` in Render uses the new `xoxb-...` token.

## 4. Hosted Demo Smoke Test

Post backend-owned demo cards to Slack:

```bash
curl -X POST https://YOUR_RENDER_SERVICE.onrender.com/demo/slack/send \
  -H "Content-Type: application/json" \
  -d '{"channel_id":"C0BBW328TEF"}'
```

Expected:

- Response includes a `session_id`.
- Response includes two posted Slack cards.
- Slack buttons return `200 OK`.
- Slack cards update after Approve / Block / Modify.

Open the Vercel frontend and click **Create Demo Session**.

Expected:

- Decision cards render.
- Approve / Block / Modify work.
- Ledger analytics update.
- Refreshing the backend process does not lose persisted sessions when PostgreSQL is enabled.

## 5. Final Judging Links

Prepare these before the demo:

```text
Frontend judging URL:
Backend health URL:
Slack channel:
Slack app Request URL:
PostgreSQL enabled? yes/no
OpenAI integration test result:
Slack live button result:
```
