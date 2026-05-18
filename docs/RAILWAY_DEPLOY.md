# Sentinel — Railway deployment guide

Three services in one Railway project:

```
sentinel-postgres          ← Railway Postgres plugin (one-click)
sentinel-gateway           ← FastAPI · Dockerfile at repo root
sentinel-dashboard         ← Next.js · dashboard/Dockerfile
```

Time to deploy: **~30 minutes** the first time.
Cost: **~$5–10/month** total ($5 Postgres + free tier covers the two web services).

---

## Pre-flight (one minute)

Make sure the `Dockerfile`, `dashboard/Dockerfile`, `railway.json`, and `dashboard/railway.json` are committed and pushed to `main`. They are as of commit `115c1c0`.

```bash
# Install Railway CLI
brew install railway     # macOS · or: npm install -g @railway/cli
railway login
```

---

## Step 1 — Create the project (5 min)

```bash
cd /Users/sankar/hackathons/transform_enterprise_ai
railway init                    # creates a new project, links the local repo
```

Pick a project name like `agent-sentinel`. The CLI prints a project URL — keep it open in a browser, that's the Railway dashboard.

---

## Step 2 — Add Postgres (1 min)

In the Railway dashboard:

1. Click **+ New** → **Database** → **Add PostgreSQL**
2. Wait ~30s for provisioning
3. Note: Railway auto-creates a `DATABASE_URL` variable referenceable as `${{Postgres.DATABASE_URL}}` from other services

---

## Step 3 — Deploy the gateway (10 min)

```bash
railway service create gateway   # creates an empty service
# Now in the dashboard, set the service config:
#   Settings → Source → Connect GitHub repo (SankarSubbayya/agent_sentinel)
#   Settings → Build → Dockerfile path: Dockerfile
#   Settings → Networking → Generate Domain (gets you a *.up.railway.app URL)
```

Set environment variables on the **gateway** service:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `SENTINEL_JWT_SIGNING_KEY` | Generate fresh: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SENTINEL_HOST` | `0.0.0.0` |
| `SENTINEL_ENV` | `prod` (disables `/v1/_test/*` endpoints AND enables the per-IP rate limiter) |
| `GEMINI_API_KEY` | **Your real key.** Public demo runs on real Gemini. Per-IP rate limit (30/min, 500/day) caps abuse — worst case ~$0.50/IP/day. |
| `SENTINEL_RATE_LIMIT_PER_MIN` | `30` (default; lower this for tighter spend control) |
| `SENTINEL_RATE_LIMIT_PER_DAY` | `500` (default; per-IP daily ceiling on Gemini-spending calls) |

Trigger the first deploy:

```bash
railway up                       # streams build + deploy logs
```

Healthcheck: open `https://<your-gateway>.up.railway.app/healthz` — should return `{"status":"ok", "gemini_configured": false, ...}`.

The first request runs `init_schema()` against the new Postgres which applies `sql/001_init.sql` + `sql/002_phase2.sql` automatically (see `gateway/app.py:lifespan`).

---

## Step 4 — Deploy the dashboard (10 min)

```bash
railway service create dashboard
# In the dashboard:
#   Settings → Source → Connect same GitHub repo
#   Settings → Source → Root Directory: dashboard/
#   Settings → Build → Dockerfile path: Dockerfile
#   Settings → Networking → Generate Domain
```

Set environment variables on the **dashboard** service:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_SENTINEL_URL` | **(build arg)** `https://<your-gateway>.up.railway.app` |

Important: `NEXT_PUBLIC_*` variables are inlined at *build time* by Next.js, so set this BEFORE the first build. Railway lets you set build-time variables via the service settings page.

Then:

```bash
railway up --service dashboard
```

Open the generated URL — the Activity page should load and show the gateway's healthz status in the top nav.

---

## Step 5 — Seed demo traffic (1 min)

Public URL is up but the ledger is empty. Pump in some realistic activity:

```bash
railway run --service gateway python scripts/seed_demo.py
```

This uses the load generator to write ~1,000 receipts at a realistic 88% allow / 7% rewrite / 5% deny distribution. Now the dashboard's Activity timeline, KPI strip, and Spend chart are all populated.

---

## Production hardening (already in place)

| Surface | What's locked down |
|---|---|
| Test endpoints | `POST /v1/_test/truncate` and `/v1/_test/tamper` return 403 when `SENTINEL_ENV=prod` |
| Gemini quota | Run with `GEMINI_API_KEY=""` (stub mode) — public traffic doesn't burn your quota |
| Hash chain | Per-agent asyncio lock + Postgres advisory lock prevent concurrent-write forks |
| Receipts | Hash-chained + HMAC-signed; `sentinel ledger verify` works against the prod DB |

## Adding the real Gemini key later

If you want one polished real-Gemini run for the submission video:

```bash
# 1. Set the key on the gateway service (Railway dashboard → Variables)
GEMINI_API_KEY=AIzaSy...

# 2. Restart the service (one-click in dashboard, or)
railway redeploy --service gateway

# 3. Run a small live-Gemini load to populate Gemini-authored rationales
railway run --service gateway python -c "
import asyncio
from scripts.load_generator import main
asyncio.run(main(total=50, concurrency=4))
"
```

Cost for the populate step: ~$0.02. Don't leave the key set for the public URL after the video — judges hitting the dashboard will spend your tokens.

---

## Quickstart cheat sheet

```bash
brew install railway
railway login
cd agent_sentinel
railway init
# (dashboard: + Database → PostgreSQL)
# (dashboard: + Service → gateway, set env vars per Step 3)
# (dashboard: + Service → dashboard, set NEXT_PUBLIC_SENTINEL_URL per Step 4)
railway up
railway run --service gateway python scripts/seed_demo.py
# done. Two public URLs ready to share.
```

## Troubleshooting

- **Gateway healthz returns 500**: check `DATABASE_URL` is the `${{Postgres.DATABASE_URL}}` reference, not the raw connection string from the Postgres service. The reference auto-resolves; raw strings drift if you re-provision Postgres.
- **Dashboard shows "Sentinel unreachable"**: rebuild the dashboard service after setting `NEXT_PUBLIC_SENTINEL_URL` — Next.js inlined the old value. `railway redeploy --service dashboard`.
- **Postgres limits**: Railway's free Postgres caps at 100 MB. The 1k-receipt seed uses ~5 MB. Plenty of room for the demo.
- **Cold starts**: free-tier services sleep after inactivity. First request after a long gap is ~10s; subsequent are normal.
