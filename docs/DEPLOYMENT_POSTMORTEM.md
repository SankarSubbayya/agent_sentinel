# Deployment Post-Mortem — Railway + Vercel

Lessons learned shipping Agent Sentinel for the **Transforming Enterprise Through AI** hackathon (May 11–19, 2026). Final topology that worked:

- **Gateway (FastAPI + Postgres):** Railway, Dockerfile build
- **Dashboard (Next.js):** Vercel
- **Database:** Railway-managed Postgres 16

Estimated time lost to deploy issues: ~5 hours, mostly fighting Railway's builder auto-detection. Most of it was avoidable with the rules below.

---

## TL;DR — the four rules

1. **Railway Railpack is sticky.** Once a service is created and Railpack auto-detects a builder, you cannot reliably switch to Dockerfile from the UI. Use **config-as-code (`*.railway.toml`)** *before* first deploy, or use **one service per repo**, or accept that you'll be deleting and recreating the service.
2. **Wrap `$PORT` in `sh -c`.** Railway injects `$PORT` as an env var, not a Docker build-arg. Container `CMD ["app", "--port", "$PORT"]` will pass the literal string `$PORT`. Wrap: `CMD ["sh", "-c", "app --port ${PORT:-8088}"]`.
3. **Vercel + Next.js needs `vercel.json`.** If the project root has no `package.json` *and* no `vercel.json`, Vercel guesses "static site" and looks for `public/`. Pin `"framework": "nextjs"` in `vercel.json` *inside the project root directory*.
4. **`NEXT_PUBLIC_*` is baked at build time.** Setting it after first deploy does nothing until you redeploy. Set every public env var **before** the first import to Vercel, or trigger a redeploy.

---

## Railway — what failed and why

### Issue 1: Builder lock-in (the 4-hour bug)

**Symptom.** Created a second Railway service for the Next.js dashboard pointing at the same repo. Railpack auto-detected Python (because of `pyproject.toml` at repo root) and started building the *gateway's* Dockerfile for the *dashboard* service. The dashboard URL served the FastAPI gateway.

**What we tried that did not work:**

- Changing Builder from Railpack → Dockerfile in the Railway service Settings UI. The dropdown showed the change but every redeploy reverted to Railpack.
- Setting `RAILWAY_DOCKERFILE_PATH=Dockerfile.dashboard` as a service env var. **This env var does not exist.** Railway docs reference it but the build system ignores it.
- Adding a root-level `Dockerfile.dashboard` whose `COPY` statements only pulled `dashboard/*`. Railpack still ran first.
- Adding a `dashboard.railway.toml` config-as-code file pinning `builder = "DOCKERFILE"` and `dockerfilePath = "Dockerfile.dashboard"`. Service Settings → Config-as-code → set path. **Builder still ran Railpack.**

**Why.** When a Railway service is created with a Nixpacks/Railpack-detected runtime, the build provider gets pinned in service metadata. The UI dropdown updates a field that the build system reads only on first deploy. Config-as-code only takes effect if the service was *originally* created in Dockerfile mode.

**What actually worked.** Pivoted the dashboard to Vercel. Took 8 minutes.

**Generic lesson.**
- **Monorepo + Railway:** create each service with its **Root Directory** set to the subfolder *before first deploy*. (Service settings → Source → Root Directory.) Railpack detection runs against that subfolder only.
- **If you must rescue a wrong-builder service:** delete the service and recreate. Don't try to coerce it. Save 4 hours of your life.
- **Better:** use Railway for one service per project (the backend) and a different platform for the frontend. Vercel for Next.js, Cloudflare Pages for static, Fly.io for any second container service.

### Issue 2: `$PORT` passed literally to the container

**Symptom.** Railway deploys reported "deployment successful" but the public URL returned `502 Bad Gateway`. Logs showed: `error: invalid port: '$PORT'`.

**Why.** Our `Dockerfile` used `CMD ["uvicorn", "sentinel.gateway:app", "--port", "$PORT"]` — Docker's exec form does not invoke a shell, so `$PORT` is not expanded. Railway injects `PORT` as an env var, but the container received the literal string.

**Fix.** Switch to shell form *or* wrap in `sh -c`:

```dockerfile
CMD ["sh", "-c", "uvicorn sentinel.gateway:app --host 0.0.0.0 --port ${PORT:-8088}"]
```

Also fixed `railway.json` `startCommand`:

```json
{ "deploy": { "startCommand": "sh -c \"npx next start -p $PORT\"" } }
```

**Generic lesson.** Anytime a deploy target injects an env var, **never** rely on Docker exec form to expand it. Always: `sh -c "..."`. The `${PORT:-8088}` fallback also makes the container runnable locally.

### Issue 3: `${{Postgres.DATABASE_URL}}` resolves to empty string

**Symptom.** Gateway service had a `DATABASE_URL` variable referencing the Railway Postgres add-on via `${{Postgres.DATABASE_URL}}`. On deploy, `DATABASE_URL` was empty. asyncpg failed: `cannot parse empty connection string`.

**Why.** We had pasted the reference with surrounding quotes (`"${{Postgres.DATABASE_URL}}"`). Railway treats the variable value as a literal string when quotes are present and skips variable interpolation.

**Fix.** Delete the variable. Re-add it with `${{Postgres.DATABASE_URL}}` and **no quotes**.

**Generic lesson.** Railway's variable-reference syntax is `${{ServiceName.VAR_NAME}}` and must be entered as the *entire* value of the field — not as a quoted string inside a larger value. If a reference shows empty after a redeploy, check for stray quotes first.

### Issue 4: `DATABASE_URL` vs `DATABASE_PUBLIC_URL`

**Symptom.** Trying to run `psql` from the laptop using `DATABASE_URL` from Railway → `could not translate host name "postgres.railway.internal"`.

**Why.** Railway's `DATABASE_URL` resolves to the *internal* hostname `postgres.railway.internal`, only reachable from inside the Railway project network. External clients (laptop, CI, Vercel) need `DATABASE_PUBLIC_URL`, which routes through a public proxy.

**Fix.**
- **Gateway-to-Postgres (intra-Railway):** use `DATABASE_URL`. Faster, no proxy.
- **Laptop, CI, external service-to-Postgres:** use `DATABASE_PUBLIC_URL`.

**Generic lesson.** Every managed Postgres on Railway/Render/Fly has both. Internal hostname for same-project services; public for everything else. Pick deliberately.

### Issue 5: Public URL 404s on `/`

**Symptom.** `https://agent-sentinel.up.railway.app/` → `{"detail":"Not Found"}`. Looks like deploy failed.

**Why.** FastAPI had `/healthz`, `/v1/...`, and `/.well-known/agent.json` routes — but no handler for `/`. The default 404 is unhelpful for a hackathon-facing URL.

**Fix.** Added a landing-page handler at `/` returning a small `HTMLResponse` with the project name and a link to `/healthz`. ~70 lines.

**Generic lesson.** **Always** add a root route for any service that will be opened in a browser by a judge or recruiter. A 404 on `/` looks like a broken deploy even when the service is healthy.

### Issue 6: Auto-generated subdomain doesn't match service name

**Symptom.** Created a service named `agent-sentinel`. Railway generated the public URL `gateway-production-234a.up.railway.app`.

**Why.** Railway's subdomain is derived from the service's `replicaId` and project context at *first deploy*, not from the service name. Renaming the service later does not change the subdomain.

**Fix.** Railway dashboard → service → Settings → Networking → **Generate Domain** with a custom subdomain (`agent-sentinel.up.railway.app`). Works for free Railway subdomains.

**Generic lesson.** Set the public subdomain explicitly via the Networking panel right after first deploy. Don't trust the auto-generated one.

---

## Vercel — what failed and why

### Issue 1: "No Output Directory named 'public' found after the Build completed"

**Symptom.** Pushed the dashboard to Vercel. Build succeeded. Deploy phase errored: `Error: No Output Directory named 'public' found after the Build completed.`

**Why.** Vercel auto-detects framework from `package.json` at the project root. The `dashboard/` subdirectory had a `package.json` but Vercel was reading it as a generic static site (no framework preset matched). Default static output is `public/`. Next.js writes to `.next/`.

**Fix.** Created `dashboard/vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "installCommand": "npm install"
}
```

Pushed, redeployed, served.

**Generic lesson.** For every Next.js project on Vercel: commit `vercel.json` with `framework: "nextjs"` **before** the first import. Vercel's auto-detect is good but not infallible, especially when the project is in a subdirectory of a monorepo.

### Issue 2: Vercel project landed under wrong team

**Symptom.** URL was `agent-sentinel-aqtf9cgd4-agent-qed.vercel.app`. We expected `agent-qed` was an old team slug from a previous project; we wanted `agent-sentinel`.

**Why.** Vercel team/org slugs are bound to the GitHub account at first login. Subsequent project names are independent, but the URL pattern is `<project>-<hash>-<team-slug>.vercel.app`. The team slug is sticky.

**Fix.** The free Vercel tier gives an alias `agent-sentinel-weld.vercel.app` (random adjective from Vercel's word list). Use that, or add a custom domain.

**Generic lesson.**
- Your Vercel team slug is forever. Pick deliberately when first creating an account.
- The clean alias (`<project>-<word>.vercel.app`) is what to share publicly.
- For real-domain projects, add a custom domain in Settings → Domains.

### Issue 3: `NEXT_PUBLIC_*` env vars not taking effect

**Symptom.** Dashboard deployed, but the timeline page showed "0 decisions in last 200 receipts" — even though the Railway gateway had thousands. Network tab showed requests going to `http://localhost:8088`.

**Why.** `NEXT_PUBLIC_SENTINEL_URL` was set in `.env.local` on the laptop but not in Vercel's project Environment Variables. `NEXT_PUBLIC_*` is **inlined at build time**, not read at runtime. The build that ran on Vercel used the default localhost fallback.

**Fix.**
1. Vercel project → Settings → Environment Variables.
2. Add `NEXT_PUBLIC_SENTINEL_URL=https://agent-sentinel.up.railway.app` for Production (and optionally Preview).
3. Trigger a redeploy (push a commit, or Deployments tab → ... → Redeploy).

**Generic lesson.**
- Any env var prefixed with `NEXT_PUBLIC_` (or any framework's public-env equivalent: `VITE_`, `REACT_APP_`, `PUBLIC_`) is **baked at build**. Setting it after the build does nothing.
- Set every public env var in the platform's env panel **before** the first build.
- After changing a public env var, you **must** redeploy.

### Issue 4: Production domain shows "Not serving traffic"

**Symptom.** Vercel UI flagged the production domain as not serving traffic, but the deployment-specific URL worked fine.

**Why.** A Vercel project's first deploy creates a deployment URL (the long hash one). The "production domain" (the clean alias like `agent-sentinel-weld.vercel.app`) is only attached after Vercel promotes a deployment to "Production". For new projects with only Preview deploys, no production URL exists.

**Fix.** Deployments tab → click the latest successful deploy → **Promote to Production**.

**Generic lesson.** First push to Vercel creates a preview deploy, not a production deploy. Promote explicitly to get the clean URL. (Pushes to `main` should auto-promote once a production branch is set, but the *first* deploy never does.)

---

## Defensive checklist before next hackathon

Print this. Tape it to the wall.

### Before opening Railway:
- [ ] Decide one-service-per-repo, or one-repo-multi-service. If multi-service, every Dockerfile lives at the *root* and `COPY`s only its own subdirectory.
- [ ] Every Dockerfile `CMD` uses `sh -c "... --port ${PORT:-DEFAULT}"`.
- [ ] Every `railway.json` has `"startCommand": "sh -c \"... $PORT\""`.
- [ ] Each FastAPI app has a `/` handler. Even a one-liner.

### When creating a Railway service:
- [ ] Set **Root Directory** before first deploy if the service is in a subfolder.
- [ ] If you want Dockerfile: create the service via the CLI (`railway up` with a Dockerfile in scope) so Railpack never runs. Don't trust the UI dropdown to switch builders.
- [ ] Set the public subdomain in Networking *immediately* after first deploy.
- [ ] Test the public URL in a browser with `/` before declaring the deploy done.

### When creating a Vercel project:
- [ ] `vercel.json` with `"framework": "nextjs"` committed to the project root *before* import.
- [ ] Set **every** `NEXT_PUBLIC_*` env var in Vercel's UI *before* triggering the first build.
- [ ] After first deploy, **promote to production** in the Deployments tab.
- [ ] Verify the clean alias URL (`<project>-<word>.vercel.app`) loads — not just the long hash URL.

### Cross-platform:
- [ ] Your frontend bundles the backend URL at build time. Confirm with `curl -s <frontend-url> | grep -oE 'https?://[^"]+'` that no `localhost:` URLs leak.
- [ ] Postgres connection string: internal hostname inside the platform, public hostname for everything else.
- [ ] Add at least one piece of seed data (a row, a policy, a user) to the live database before the demo — empty UIs look broken.

---

## What I'd do differently

**1. Pick the deploy target by app shape, not platform familiarity.**

| App shape | Best fit | Why |
|---|---|---|
| Next.js, Remix, SvelteKit, Astro | **Vercel** | First-class framework detection; build-time env baking; instant rollback |
| Long-running Python/Node service + Postgres | **Railway** or **Render** | Managed Postgres in the same project, internal networking |
| Static site + a couple of edge functions | **Cloudflare Pages** | Free tier covers most hackathons |
| One container, no DB | **Fly.io** | Best Dockerfile UX; closest to "scp a binary" |

Don't try to make Railway do Vercel's job (Next.js) or Vercel do Railway's job (long-running Python). The hour you spend fighting the wrong platform is the hour you don't spend recording your video.

**2. Deploy at the end of Day 1, not Day 7.**

Every hackathon I deploy on the last day, I lose hours to platform quirks. The fix is brain-dead: spin up an empty FastAPI `/healthz` and an empty Next.js `<h1>Hello</h1>` on Day 1, push them, get the public URLs, *then* iterate. Every commit is a deploy from then on. Bugs surface when changes are small.

**3. Two `.env.example` files, not one.**

One for local (`localhost:8088`), one for production (`https://your-gateway.up.railway.app`). The diff between them is the deploy config — much easier to spot what's missing than reading platform docs.

**4. Add a one-page `DEPLOYMENT.md` per project from the start.**

The information density of "what URL is what, where the env vars live, how to redeploy each piece" is non-trivial. Writing it down on Day 1 saves you on Day 7 when you're tired and the demo is in 2 hours.
