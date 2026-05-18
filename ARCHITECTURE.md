# Sentinel — As-Built Architecture

> Companion to [PRD.md](PRD.md) (design intent) and [CLAUDE.md](CLAUDE.md) (deep context). This document describes only what is implemented and running as of 2026-05-17.

## TL;DR

Sentinel is a single FastAPI process backed by Postgres, with a Next.js operator dashboard. Every MCP-shaped tool call from an enterprise AI agent flows through a four-stage decision pipeline, gets recorded as a hash-chained signed audit receipt, and emits a per-business-unit cost event.

```
┌──────────────────┐
│  Agent fleet     │  MCP-shaped envelope
│  (Gemini /       │  {agent_id, session_id, tool, args}
│   Claude / etc.) │
└────────┬─────────┘
         │ HTTPS POST /v1/tools/call            ▲
         ▼                                       │ ToolCallResponse
┌─────────────────────────────────────────────────────────────────┐
│  SENTINEL CORE  (FastAPI · src/sentinel/gateway/)               │
│                                                                 │
│   1. Static engine    ── <5ms ──▶ regex denylist · role ACL    │
│      static_engine.py              · refund cap · PII regex     │
│                                                                 │
│   2. Drift signal     ── ~0ms ──▶ injection markers ·          │
│      drift.py                       tool-vs-declared-goal       │
│                                                                 │
│   3. Flash gate       ── <100ms ▶ Gemini 2.5 Flash             │
│      flash.py                       response_schema=GateDecision│
│                                     thinking_budget=0           │
│                                     (deterministic stub if no   │
│                                      GEMINI_API_KEY)            │
│                                                                 │
│   4. Pro escalation   ── <2s ───▶ Gemini 2.5 Pro                │
│      pro.py                         cached_content=<policy>     │
│                                     fires when escalate=true OR │
│                                     confidence<0.85 OR drift    │
│                                                                 │
│   5. Audit ledger     ─────────▶  per-agent hash chain          │
│      audit/ledger.py                prev_hash → self_hash       │
│                                     HMAC-SHA256 signature       │
│                                                                 │
│   6. Cost meter       ─────────▶  cost_event {bu, base,         │
│      cost/meter.py                  gemini, total}              │
└─────────┬───────────────────────────────────────────────────────┘
          │ Postgres · agents, policy_docs, audit_receipts, cost_events
          ▼
   Operator dashboard (Next.js · http://localhost:3030)
   Activity · Brief · Receipts · Spend · Red team · Policies
```

## Two ways to drive the system

### A. Direct tool-call API (machine-to-machine)
`POST /v1/tools/call` with a pre-formed MCP envelope. Any agent framework that already speaks `tools/call` is a drop-in client.

### B. LLM-driven brief API (the AI-feeds-the-input mode)
`POST /v1/agents/run` with a natural-language brief like *"Find Q3 competitor pricing and email vp-sales"*. A Gemini 2.5 Flash agent (with function-calling) picks tools turn-by-turn. **Every tool call still flows through the same gate_and_record pipeline** in (A) — so audit + cost coverage is identical whether the agent is hand-driven or LLM-driven.

```
POST /v1/agents/run
  → agent_runner/runner.py
      Gemini Flash (function-calling, role-scoped tool catalog)
      ↓ picks tool
      gateway/pipeline.py · gate_and_record()  ← same pipeline as A
      ↓ returns decision
      mock_execute()                            ← deterministic mock result
      ↓ feeds back to Gemini
      … loop until done or max_steps …
```

## File map (every PRD requirement → file)

| PRD req | Concern | File |
|---|---|---|
| F1–F4  | MCP gateway, ToolCallRequest, response shape | [src/sentinel/gateway/app.py](src/sentinel/gateway/app.py), [src/sentinel/models.py](src/sentinel/models.py) |
| F5     | Static rules <5ms                              | [src/sentinel/gating/static_engine.py](src/sentinel/gating/static_engine.py) |
| F6     | Flash gate w/ structured output                | [src/sentinel/gating/flash.py](src/sentinel/gating/flash.py) |
| F7     | Pro escalation with Cached Content             | [src/sentinel/gating/pro.py](src/sentinel/gating/pro.py) |
| F8     | Drift detection                                 | [src/sentinel/gating/drift.py](src/sentinel/gating/drift.py) |
| F9–F13 | PolicyPipe (PDF → Files API → CachedContent)   | [src/sentinel/policy_pipe/](src/sentinel/policy_pipe/) (5 modules) |
| F14    | Receipt schema                                  | [sql/001_init.sql](sql/001_init.sql), [src/sentinel/models.py](src/sentinel/models.py) |
| F15    | Per-agent hash chain + HMAC                    | [src/sentinel/audit/ledger.py](src/sentinel/audit/ledger.py) |
| F16    | Query endpoint                                  | gateway `/v1/receipts` |
| F17    | Append-only receipts                            | `INSERT`-only DAO in [audit/ledger.py](src/sentinel/audit/ledger.py) |
| **NEW** | Hash-chain + HMAC verifier (CLI, exits non-zero on tamper) | [src/sentinel/audit/verify.py](src/sentinel/audit/verify.py), `sentinel ledger verify` |
| F18–F19| Cost events + BU rollup                         | [src/sentinel/cost/meter.py](src/sentinel/cost/meter.py) |
| F20    | Dashboard bar chart                             | [dashboard/src/app/cost/page.tsx](dashboard/src/app/cost/page.tsx) |
| F21    | Live timeline via SSE                           | gateway `/v1/events/stream` + [dashboard/src/app/page.tsx](dashboard/src/app/page.tsx) |
| F22    | Blocked-action replay                           | [dashboard/src/app/receipts/page.tsx](dashboard/src/app/receipts/page.tsx) (drawer) |
| F23    | BU cost rollup                                  | [dashboard/src/app/cost/page.tsx](dashboard/src/app/cost/page.tsx) |
| F24    | Red-team console                                | [dashboard/src/app/redteam/page.tsx](dashboard/src/app/redteam/page.tsx) |
| **NEW** | LLM-driven agent runner (beyond original PRD)  | [src/sentinel/agent_runner/](src/sentinel/agent_runner/), `/v1/agents/run`, [dashboard/src/app/agent/page.tsx](dashboard/src/app/agent/page.tsx) |

## Data model (Postgres)

```sql
agents               agent_id (PK), name, bu, role, declared_goal
policy_docs          id, name, version, gemini_file_id, cache_id,
                     cache_expires_at, domain_tags[], source_sha256
audit_receipts       receipt_id, agent_id, session_id, tool, args_hash,
                     decision, decided_by, confidence, escalated,
                     rationale, rationale_hash, policy_versions_used (JSONB),
                     gemini_cache_ids[], prev_hash, self_hash, signature,
                     latency_ms, created_at
cost_events          receipt_id (FK), bu, tool, base_cost_usd,
                     gemini_cost_usd, total_cost_usd, created_at
```

Indexes: `(agent_id, created_at DESC)` and `session_id` on receipts for compliance pulls; GIN on `domain_tags` for PolicyPipe lookups.

## HTTP surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/tools/call` | Gate one tool envelope; persist receipt + cost event |
| `POST` | `/v1/agents/run` | LLM-driven brief → multi-step run; every step gated |
| `GET`  | `/v1/receipts` | Filterable receipt browser (agent_id, bu, tool, decision) |
| `GET`  | `/v1/cost/rollup?days=N` | Per-BU spend, split base vs Gemini |
| `GET`  | `/v1/policies` | Policy library |
| `POST` | `/v1/policies/upload` | PDF → PolicyPipe → cached policy doc |
| `GET`  | `/v1/events/stream` | SSE timeline (1s poll-then-diff under the hood) |
| `GET`  | `/healthz` | Liveness + `gemini_configured` flag |

## Stub mode vs. live Gemini

Sentinel runs end-to-end **without** `GEMINI_API_KEY`. Both the Flash gate and the Pro escalation have deterministic stub fallbacks that mirror the real model's decision logic. **Critical invariant:** the stub Pro never weakens a Flash deny — demo correctness does not depend on a live API call.

When `GEMINI_API_KEY` is set, the same code paths call the real models:
- Flash uses `response_schema=GateDecision` + `thinking_budget=0` for sub-100ms latency
- Pro uses `cached_content=<cache_name>` to skip ~75% of policy tokens
- The agent runner uses Gemini Flash function-calling with role-scoped tool catalogs

## Defensible technical choices

| Choice | Why |
|---|---|
| **Two-tier Flash + Pro** | Flash gates every call; Pro consumes whole policy docs on the ~3–5% that escalate. Cached Content makes per-call governance economically viable. |
| **Hash-chained, HMAC-signed receipts** | Tamper-evident without a blockchain. Rewriting one row breaks every later receipt for the same agent. An external auditor verifies with the signing key alone. |
| **Static engine before Flash** | Regex denylists, ACL, refund cap catch the obvious cases in <5ms with zero LLM tokens. |
| **Drift detector pre-Flash** | Cheap signal (regex + goal-string match) escalates the indirect-prompt-injection case to Pro instead of letting Flash decide alone. |
| **PolicyPipe is 5 files, ~600 LOC** | No chunking, no vector DB, no LangChain — direct Gemini Files API + CachedContent. Sponsor-visible. |
| **MCP-shaped envelope** | Drop-in for any agent framework that already speaks `tools/call`. |
| **One FastAPI process + Postgres** | Single durable store for ledger + cost + policy catalog. SSE is poll-then-diff against Postgres — no separate event bus. |

## What's *not* in v1 (Phase 2 roadmap)

- Multi-region replicated audit ledger
- Customer-managed encryption keys
- Native adapters for LangGraph / CrewAI / Anthropic Agent SDK / Google ADK
- Policy authoring UI (currently PDF-in only)
- Distributed receipt-chain anchoring (optional on-chain settlement of the receipt root hash — connects to the user's Arc/Circle work from `ARC_DataPiper`)

## Repo layout

```
.
├── ARCHITECTURE.md           ← this file
├── PRD.md                    ← product requirements (design intent)
├── CLAUDE.md                 ← long-form context for Claude sessions
├── README.md                 ← public-facing project description
├── pyproject.toml            ← agent-sentinel, Python ≥3.12
├── docker-compose.yml        ← Postgres 16 (alt: local brew Postgres)
├── sql/
│   └── 001_init.sql          ← single-file schema, idempotent
├── src/sentinel/
│   ├── config.py             ← pydantic-settings, .env-driven
│   ├── models.py             ← wire-level Pydantic models
│   ├── db/engine.py          ← async SQLAlchemy + asyncpg
│   ├── gating/
│   │   ├── static_engine.py  ← regex / ACL / cap (<5ms)
│   │   ├── drift.py          ← injection markers + goal mismatch
│   │   ├── flash.py          ← Gemini Flash gate (+ stub)
│   │   └── pro.py            ← Gemini Pro escalation (+ stub)
│   ├── policy_pipe/
│   │   ├── extractor.py      ← Flash multimodal: PDF → ExtractedPolicy
│   │   ├── catalog.py        ← policy_docs CRUD
│   │   ├── cache_builder.py  ← Files API + CreateCachedContent
│   │   ├── loader.py         ← tool family → cache_ids
│   │   └── refresher.py      ← TTL refresh
│   ├── audit/ledger.py       ← hash-chained HMAC receipts
│   ├── cost/meter.py         ← per-call cost + BU rollup
│   ├── gateway/
│   │   ├── pipeline.py       ← gate_and_record (reusable from runner)
│   │   └── app.py            ← FastAPI surface
│   ├── agent_runner/
│   │   ├── tools.py          ← catalog + mock executors
│   │   └── runner.py         ← Gemini function-calling loop (+ stub)
│   ├── demo_agents/
│   │   ├── runner.py         ← 6-beat PRD demo script
│   │   └── seed_pdfs.py      ← generate demo policy PDFs (no reportlab)
│   └── cli.py                ← `sentinel <subcommand>`
└── dashboard/                ← Next.js 14.2 + Tailwind + vendored shadcn
    └── src/app/
        ├── page.tsx          ← Activity (live timeline)
        ├── agent/page.tsx    ← Brief (LLM-driven agent runner)
        ├── receipts/page.tsx ← Receipts (filterable + drawer)
        ├── cost/page.tsx     ← Spend (stacked BU chart)
        ├── redteam/page.tsx  ← Red team (hand-craft calls)
        └── policies/page.tsx ← Policies (library + upload)
```

## Quickstart (verbatim)

```bash
# 1. Postgres
createdb -h localhost agent_sentinel       # or: docker compose up -d postgres

# 2. Backend
cp .env.example .env                       # set DATABASE_URL, signing key
uv sync
uv run sentinel init-db
uv run sentinel serve --port 8088

# 3. Demo
uv run sentinel demo run                   # walks the 6 PRD beats
# or:
uv run sentinel agent run agent-sales-01 "Find Q3 competitor pricing and email vp-sales"

# 4. Dashboard
cd dashboard && cp .env.local.example .env.local && npm install
PORT=3030 npm run dev                      # http://localhost:3030
```

## Verified end-to-end (stub mode, 2026-05-17)

```
[OK] happy_path__sales_competitor_pricing     -> allow    (5ms)
[OK] policy_violation__finance_pii_external   -> rewrite  (2ms)
[OK] red_team__ops_prompt_injection           -> deny     (4ms)
[OK] ops_legit_small_refund                   -> allow    (2ms)
[OK] ops_static_deny_refund_cap               -> deny     (2ms)
[OK] sales_internal_summary                   -> allow    (2ms)
```

Plus three LLM-driven agent-runner scenarios across all three roles (Sales, Finance, Ops). All receipts persist with hash-chain integrity and feed the BU cost rollup.
