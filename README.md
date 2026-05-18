# Agent Sentinel

**Gemini-powered governance plane for enterprise AI agents.**

Built for the [Transforming Enterprise Through AI](https://lablab.ai) hackathon — May 11–19, 2026.
Track 2 (AI Agents with Google AI Studio) primary, Track 1 (Agent Security & AI Governance) secondary.

---

## What it is

Enterprises deploying AI agents face three blockers: no audit trail, no policy enforcement, no cost accountability. Agent Sentinel solves all three.

Drop it in front of any MCP-speaking agent and every tool call is:

1. **Gated** by Gemini 2.5 Flash in under 100 milliseconds
2. **Escalated** to Gemini 2.5 Pro for full-policy-document reasoning when ambiguous
3. **Recorded** as a hash-chained, HMAC-signed receipt that cites the exact policy version used
4. **Costed** as a per-business-unit event for chargeback

Sentinel detects indirect prompt injection by reasoning over the agent's recent action history — blocking exfiltration before it ships. Built on Gemini's 1M-context window and Cached Content (~75% token cost savings on stable policy bundles).

> Cloudflare for AI agents. Built on Gemini.

## The three buyers, one demo

- **Compliance officers** get queryable evidence with cited policy versions
- **CISOs** get inline policy enforcement and prompt-injection defense
- **CFOs** get per-BU cost attribution and chargeback

## Why Gemini

Two-tier model usage — the Track 2 Gemini-native story:

- **Gemini 2.5 Flash** — sub-100ms inline gate with `response_schema` structured output, thinking budget zeroed for latency
- **Gemini 2.5 Pro** — long-context policy reasoning over the full policy book (no chunking, no RAG drift) on the ~3-5% of calls that escalate
- **Cached Content** — ~75% token cost savings on stable policy bundles, refreshed every 6h
- **Files API** — authoritative policy storage with multimodal extraction

## Architecture

```
Agent fleet ─MCP─► Sentinel core ─► External tools
                       │
                       ├── Static policy engine (regex/ACL, <5ms)
                       ├── Drift detector (recent-history signal)
                       ├── Flash gate (every call, <100ms)
                       ├── Pro reasoner (escalations, full policy docs via Cached Content)
                       ├── Audit ledger (Postgres, hash-chained HMAC receipts)
                       └── Cost meter (per-BU, $/call rules)

          Operator dashboard (Next.js) — timeline, replay, BU rollup, red-team console
```

Full architecture: [CLAUDE.md](CLAUDE.md) · Product spec: [PRD.md](PRD.md)

## Layout

```
src/sentinel/
  config.py              # pydantic-settings, loads .env
  models.py              # ToolCallRequest, GateDecision, ToolCallResponse, AgentRecord
  db/                    # async SQLAlchemy engine + sql/001_init.sql bootstrap
  gating/
    static_engine.py     # regex denylists, role ACL, refund cap (<5ms)
    drift.py             # injection markers + tool-vs-goal mismatch
    flash.py             # Gemini Flash inline gate (+ key-less stub fallback)
    pro.py               # Gemini Pro escalation w/ Cached Content (+ stub fallback)
  policy_pipe/
    extractor.py         # Flash multimodal: PDF → ExtractedPolicy
    catalog.py           # policy_docs CRUD
    cache_builder.py     # Files API + CachedContent create/refresh
    loader.py            # tool_family → cache_ids
    refresher.py         # TTL refresh (cron-friendly)
  audit/ledger.py        # hash-chained HMAC receipts
  cost/meter.py          # per-call cost + BU rollup
  gateway/app.py         # FastAPI surface (only HTTP entrypoint)
  demo_agents/runner.py  # the PRD §A demo script as 6 runnable beats
  demo_agents/seed_pdfs.py # generates 3 policy PDFs without external deps
  cli.py                 # `sentinel <subcommand>`

sql/001_init.sql         # schema (agents, policy_docs, audit_receipts, cost_events)
docker-compose.yml       # Postgres 16 (alternative to local brew Postgres)
dashboard/               # Next.js 14 + Tailwind + shadcn operator dashboard
```

---

## Quickstart

### 1. Postgres

Pick one:

```bash
# Option A — local Postgres 16 already running (brew)
createdb -h localhost agent_sentinel

# Option B — Docker
docker compose up -d postgres
```

### 2. Backend

```bash
cp .env.example .env
# edit .env — set DATABASE_URL, generate SENTINEL_JWT_SIGNING_KEY
#   python -c "import secrets; print(secrets.token_hex(32))"
# GEMINI_API_KEY is optional for the smoke loop (stub fallback) but
# required for PolicyPipe ingestion and real Pro escalation.

uv sync
uv run sentinel init-db
uv run sentinel serve --port 8088
```

Healthcheck:

```bash
curl -s http://127.0.0.1:8088/healthz | python3 -m json.tool
```

### 3. Walk the demo

In another terminal:

```bash
uv run sentinel demo run --sentinel-url http://127.0.0.1:8088
```

Expected output — 6 beats, all `[OK]`:

```
[OK] happy_path__sales_competitor_pricing             -> allow
[OK] policy_violation__finance_pii_external           -> rewrite
[OK] red_team__ops_prompt_injection                   -> deny
[OK] ops_legit_small_refund                           -> allow
[OK] ops_static_deny_refund_cap                       -> deny
[OK] sales_internal_summary                           -> allow
```

### 4. Dashboard

```bash
cd dashboard
cp .env.local.example .env.local
npm install
npm run dev    # http://localhost:3000
```

Five pages: live timeline (`/`), filterable receipts (`/receipts`),
BU cost rollup (`/cost`), red-team console (`/redteam`), policy library (`/policies`).

### 5. Policy ingestion (requires GEMINI_API_KEY)

```bash
uv run sentinel demo seed-policies --out-dir demo_policies
uv run sentinel policy upload demo_policies/data_handling_v3.2.pdf
uv run sentinel policy upload demo_policies/refund_authority_v1.4.pdf
uv run sentinel policy upload demo_policies/vendor_disclosure_v2.0.pdf
uv run sentinel policy list
```

Once policies are cached, the next Pro escalation will carry their
`cache_id` in the receipt's `gemini_cache_ids` field and `policy_versions_used` will be populated with cited names + versions.

### 6. Audit export + verify

```bash
uv run sentinel ledger export --out receipts.jsonl
uv run sentinel ledger verify                       # verify in-place against Postgres
uv run sentinel ledger verify --source jsonl --file receipts.jsonl  # verify an export
```

The verifier walks every receipt, recomputes the `self_hash` from canonical
fields, re-derives the HMAC signature with the signing key, and checks each
`prev_hash → self_hash` link in the per-agent chain. Tampering with one byte
of a stored receipt (e.g. rewriting a `rationale`) is detected: the chain
prints `BROKEN`, the verifier exits non-zero, and the specific receipt and
issue are reported. This is the runnable proof behind the
*"tamper-evident audit trail"* claim.

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/tools/call` | MCP-shaped tool envelope → `allow / deny / rewrite` + receipt |
| GET  | `/v1/receipts` | Filterable receipt browser (agent_id, bu, tool, decision) |
| GET  | `/v1/cost/rollup?days=N` | Per-BU spend, split base vs Gemini |
| GET  | `/v1/policies` | Policy library |
| POST | `/v1/policies/upload` | PDF → PolicyPipe → cached policy doc |
| GET  | `/v1/events/stream` | SSE live timeline (1s poll cadence under the hood) |
| GET  | `/healthz` | Liveness + Gemini-configured flag |

## Stub mode vs live Gemini

Sentinel runs end-to-end **without** a Gemini API key — Flash and Pro both
fall back to deterministic stub gates so you can exercise the gateway,
audit ledger, cost meter, and dashboard against real Postgres. When
`GEMINI_API_KEY` is set, the same code path calls the real models.

The stub Pro will **never weaken** a Flash deny — it can only confirm or
further restrict, so demo correctness doesn't depend on a live API call.

## Demo (2:30)

| t | Beat |
|---|---|
| 0:00 | Three Gemini agents (Sales Researcher, Finance Analyst, Customer Ops) routed through Sentinel |
| 0:20 | **Happy path** — Sales Researcher fetches competitor pricing, allowed, $0.003 charged to Sales BU |
| 0:50 | **Policy violation** — Finance Analyst tries to email PII to a vendor; rewritten to redacted form, citing Data Handling Policy |
| 1:30 | **Red team** — Prompt injection in a refund memo; Pro upholds Flash deny, drift signal cited |
| 1:55 | **Compliance pull** — Filter receipts by agent + decision |
| 2:15 | **CFO view** — BU spend stacked bar (`base_usd` vs `gemini_usd`) |

## Status

Working vertical slice as of D6 (2026-05-16). All six demo beats verified
end-to-end. Polishing for May 19 submission.

## License

MIT
