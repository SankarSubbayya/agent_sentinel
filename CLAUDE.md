# Transforming Enterprise Through AI — Project Context

## The Hackathon

**Event:** Transforming Enterprise Through AI (Build AI Agents for Security, Edge & Robotics)
**Dates:** May 11–19, 2026 (Build phase). Demos & awards May 19 at AI & Big Data Expo North America, San Jose McEnery Convention Center.
**Format:** Hybrid (online + onsite May 18–19).
**Prize pool:** $10,000 total.

### Tracks

1. **🔐 Agent Security & AI Governance** — guardrails, observability, access control, audit trails, red-teaming for agentic systems.
2. **🤖 AI Agents with Google AI Studio (Gemini)** — multi-agent systems on Gemini, long-context document processing, code/dev workflow agents, internal AI tools, enterprise integrations. **Sponsor prizes: $5k / $3k / $2k.**
3. **🤖 Robotics & Simulation** — robotics control, simulation envs, digital twins, VLMs, human-robot collaboration.
4. **📊 Data & Intelligence** — RAG over proprietary data, AI data pipelines, NL analytics agents, anomaly detection, knowledge graphs.

### Judging Criteria
Application of Technology • Presentation • Business Value • Originality

### What to Submit
Title, short + long description, tags, cover image, **video presentation**, slide deck, public GitHub repo, deployed demo + URL.

---

## Reference: Prize Patterns from `agentic_economy/` Hackathon

> **Reference only — do NOT copy these projects.** The user has placed the winning entries in [/Users/sankar/hackathons/agentic_economy/](../agentic_economy/) so we can study the *shape* of a winning Gemini-sponsor submission (architecture, demo flow, business framing). Our project must be original.

Two projects in that folder won **Google Gemini sponsor prizes** at the agentic_economy hackathon:
- 🥇 **`mev-payment-app`** — 1st place
- 🥈 **`gas-oracle`** — 2nd place

Useful blueprint for what wins a Gemini sponsor prize.

### 🥇 `mev-payment-app` — Gemini sponsor prize, 1st place
- **Pitch:** "AI agents pay for their own data via off-chain micropayments, settled on-chain in batches."
- **Flow:** `vectorblock.io/mempool` SSE → LLM agent (Claude Sonnet 4, via AIsa.one + ANTHROPIC_API_KEY in `.env.example`) analyzes MEV risk per swap → charges $0.01 to Nitrolite (Rust ERC-7824 state channel) → at $5 accumulated, settles on Circle Arc USDC via Flashbots.
- **Stack:** Docker compose, Nitrolite (Rust, port 8082), FastAPI backend (8001), nginx frontend (3020), MCP server exposing mempool tools to the agent.
- **Why it won:** Working real-money loop. Nitrolite delivers O(channels) on-chain cost (not O(transactions)) — ~50μs/state update, ~20K updates/core/sec, Pickhardt-Richter routing over 1M channels, Bellman-Ford rebalancing. Defensible scaling story + live demo.
- **Note:** Despite the prize being "Gemini," the agent runtime is Claude. The award rewarded the *agent-pays-per-query economic primitive*, not the model choice.

### 🥈 `gas-oracle` — Gemini sponsor prize, 2nd place
- **Pitch:** "Distributed gas/parking price oracle with an autonomous agent that shops for the cheapest service in real time."
- **Flow:** Users report real prices → on-chain consensus → routing-agent script (`scripts/routing-agent.ts`) autonomously queries oracle endpoints, pays per query via Circle x402 batching, settles on Arc.
- **Stack:** Next.js 16 (React 19) + TypeScript, `@circle-fin/x402-batching`, `@gemini-wallet/core` (wallet integration — this is where "Gemini" comes in), Mapbox GL, Supabase, Vercel, viem, Privy auth.
- **Why it won:** Live testnet demo of an agent autonomously discovering and paying for cheapest gas. Proof that nanopayments unlock agent commerce.
- **Note `AGENTS.md`:** Repo flags Next.js 16 has breaking changes vs. training data — read `node_modules/next/dist/docs/` before generating code.

### Other agentic_economy projects (context)

| Project | One-liner | Sponsor angle |
|---|---|---|
| `agentic-ad-exchange` | Multi-agent ad auction (Gemini 2.5-Flash buyer/seller agents via LangGraph), Circle DCW USDC settlement on Arc. | Gemini sponsor — Gemini agents in HFT-style auction loop, typed Zod→Gemini schema layer. |
| `arcade` | In-game dynamic billboards. Brand agents bid; winning creative rendered with **Gemini image gen**, streamed as 3D textures. | Gemini sponsor — novel Gemini image-gen use beyond chat. |
| `cairn` | Nanopayment oracle for sensor networks. Operators stake USDC, customer agents buy verified readings via x402, MAD outlier detection slashes Byzantine sensors. | Circle technical excellence. |
| `ShadowNPM` | Autonomous npm supply-chain auditor — 6-phase LLM pipeline returns exploit verdicts as runnable Vitest tests; gated by x402 nanopayments. | Circle nanopayments — sub-cent per query economics. |

### Common pattern that wins
- **Real working demo** (testnet or local) with end-to-end loop visible
- **Agent autonomy** (not just chat — agents *do* something with consequences)
- **Crisp economic / business argument** (one slide explains why the model scales)
- **Hardware-style metrics** (μs latency, $/query, throughput numbers, settlement cost)

---

## User's Past Hackathon Portfolio (`/Users/sankar/hackathons/`)

A map of what's been built — useful for picking a NEW direction without retreading.

### Already uses Gemini
- **Gemini0321 / TeleStudio** — multi-agent video studio (Gemini 2.5 Flash "Director", Veo 3.1, ElevenLabs). Telegram → MP4 via Remotion.
- **AltVision (hack-grocket)** — AI glasses for blind/low-vision users; native Gemini audio + RocketRide pipelines for OCR, intersection safety, food labels.
- **AlphaVector** — geospatial H3 outbreak monitoring (S/SE Asia monsoon); streaming Gemini agent investigates Earth observation evidence.

### Healthcare cluster
CareCompanion, BetaFund-CareCompanion, CareGraph (Neo4j+Bland AI), Sentinel Health (`gemma4`, offline triage), CareScribe (`reboot-agent-wiki`, `token_router_project`), Village Healer (`amd_hackathon`, 4 MCP servers).

### Agent infrastructure / OpenClaw
agent_toolkit (Web Researcher), ClawIntel (sales battle cards), Shopify Competitor Monitor, Invisible Census (SF unsheltered tracker), Meeting Agent (production system, 57% test coverage), ReplayAI (record/replay agent runs), Claw Chief of Staff.

### Data + economics (Arc/Circle nanopayment patterns user knows)
- **ARC DataPiper** — Observer Agent ($0.0001/pulse) validates streams, Fixer Agent ($0.001 hire + $0.005 success bounty) repairs them, Gemini verifies fixes in sandbox.
- **Midstream** — pay-for-outcomes LLM inference: buyer's quality oracle scores 32-token chunks at $0.0005 USDC, cuts off mid-sentence if quality drops.

### Brand / sales intel
FitCheck (brand perception + AI focus group), BidRadar (SAM.gov bid qualifier), Connectify (founder network), Market Pulse Agent (`shipto_prod`).

### Misc
City Frame (SF travel planner), EverMemOS (memory system), moblio, PlushPilot (`zero-to-agent`), blartclaw (CCTV), vercelhack.

### Reusable foundations the user already has
- Multi-agent orchestration (Meeting Agent, CareGraph, TeleStudio, ClawIntel)
- Gemini streaming + voice I/O (TeleStudio, AltVision)
- Safety gating architecture (CareScribe MedGemma review→publish flow)
- Data validation patterns (ARC DataPiper)
- OpenClaw skill + MCP server boilerplate (7+ ref implementations)
- Arc/Circle nanopayment plumbing (ARC DataPiper, Midstream)

### Gaps worth exploiting
- **Agent governance & security tooling** (Track 1 is wide open and the user hasn't built here)
- Enterprise workflow automation with **audit trails**
- Robotics/sim (Track 3 — no prior projects)
- Deep-RAG over proprietary corporate knowledge with citations + ACL

---

## Current State: `transform_enterprise_ai/`

Initial scaffold:
- [pyproject.toml](pyproject.toml) — `agent-sentinel`, Python ≥ 3.12, no deps yet
- [main.py](main.py) — placeholder entry point
- [README.md](README.md) — public-facing project description
- [PRD.md](PRD.md) — full product requirements doc
- `.env` (gitignored) — Gemini API key + Postgres URL + Sentinel signing key go here
- Git repo on `main`, pushed to https://github.com/SankarSubbayya/agent_sentinel

---

## Recommended Project — `Sentinel`: Agent Governance Plane for the Enterprise

> Track 2 (Gemini) primary, Track 1 (Governance) secondary — submit to Track 2 to compete for the $5k sponsor prize, but pitch covers both judging surfaces.

### One-liner
A **Gemini-powered control plane** that sits between enterprise multi-agent systems and the outside world: every tool call, every data fetch, every external API hit goes through Sentinel, which (a) **classifies and gates** the action against policy, (b) **records an immutable audit trail** with cited evidence, and (c) **assigns a per-call cost** so finance can chargeback agent activity to business units.

### Why this wins this specific hackathon
| Judging axis | How Sentinel scores |
|---|---|
| Application of Technology | Gemini 2.5 Pro (long-context policy reasoning) + Gemini Flash (fast inline gating, <100ms). Two-tier model usage is a first-class Gemini story. |
| Presentation | Live demo: spin up an "evil" agent that tries to exfiltrate data → Sentinel blocks it → audit log shows the reasoning chain. Then show a legit cross-system workflow flowing through. |
| Business Value | Every Fortune 500 deploying agents has *no* answer to "who approved this action" or "how much does our agent fleet cost per BU per quarter." Sentinel is that answer. |
| Originality | Most governance demos are read-only dashboards. Sentinel is *in-line* — it gates execution and produces a per-action receipt with Gemini-cited justification. Combines safety-gating (CareScribe pattern user has) with per-call economic accounting (ARC DataPiper / Midstream patterns user has). |

### Architecture (mostly things the user has already shipped pieces of)

```
┌─────────────────┐                                    ┌────────────────┐
│ Enterprise      │   tool call (MCP envelope)         │ External tool  │
│ Agent Fleet     │ ──────────────► Sentinel ────────► │ (CRM, email,   │
│ (Gemini, Claude │ ◄── allow|deny|rewrite ──         │  DB, web, etc.)│
│  Anthropic SDK) │                                    └────────────────┘
└─────────────────┘                       │
                                          ▼
              ┌───────────────────────────────────────────────┐
              │ Sentinel core (FastAPI + Gemini Flash gate)   │
              │ ┌──────────────────────────────────────────┐  │
              │ │ Policy reasoning  (Gemini 2.5 Pro,       │  │
              │ │   long-context: company policies + role  │  │
              │ │   playbooks + recent agent history)      │  │
              │ └──────────────────────────────────────────┘  │
              │ ┌──────────────────────────────────────────┐  │
              │ │ Audit ledger  (Postgres + content-       │  │
              │ │   addressed receipts; every receipt      │  │
              │ │   carries Gemini's cited justification)  │  │
              │ └──────────────────────────────────────────┘  │
              │ ┌──────────────────────────────────────────┐  │
              │ │ Cost meter  (per-BU chargeback,          │  │
              │ │   $/call rules — reuse Midstream model)  │  │
              │ └──────────────────────────────────────────┘  │
              └───────────────────────────────────────────────┘
                                          │
                                          ▼
                          Operator dashboard (Next.js)
                          - live agent timeline
                          - blocked-action replay
                          - cost-by-BU rollup
                          - red-team console
```

### Demo script (the thing the judges actually watch)
1. **Setup (10s):** Three Gemini agents — "Sales Researcher", "Finance Analyst", "Customer Ops" — each connected through Sentinel.
2. **Happy path (30s):** Sales Researcher pulls competitor pricing from web → Sentinel gates, allows, records, charges Sales BU $0.003. Live tile updates.
3. **Policy violation (40s):** Finance Analyst tries to send raw customer PII to a third-party email → Sentinel blocks, returns a Gemini-authored explanation citing internal policy §4.2, suggests a redacted alternative, agent retries successfully.
4. **Red team (40s):** Inject a prompt-injection that tells Customer Ops agent to email a refund to attacker@evil.com → Sentinel detects intent drift via Gemini Pro reasoning over recent agent history, blocks, alerts.
5. **Audit pull (20s):** Compliance officer queries "show me every action Customer Ops took yesterday touching customer email" → returns cited timeline.
6. **CFO view (20s):** "Agent spend by BU this week" → bar chart, drill down to per-call cost.

### MVP scope for May 11–18 (7 build days)
- **Day 1–2:** FastAPI Sentinel core with one MCP-style tool envelope, Gemini Flash inline gate, Postgres audit table.
- **Day 3:** PolicyPipe ingestion (Flash extractor, Gemini Files API, Cached Content, Postgres `policy_docs`). Gemini 2.5 Pro escalation path wired through PolicyPipe.
- **Day 4:** Cost meter + chargeback ledger (lift from Midstream/ARC DataPiper patterns).
- **Day 5:** Three Gemini demo agents wired through. Drift detector for prompt-injection demo.
- **Day 6:** Next.js operator dashboard (reuse gas-oracle / Meeting Agent UI scaffolding).
- **Day 7:** Red-team scenarios + the demo script + the video.
- **Day 8 (May 18 hybrid build):** Polish, deploy, record final demo. Submit by May 19 morning.

### Stack
- **Models:** Gemini 2.5 Pro (policy reasoning), Gemini 2.5 Flash (inline gate + PDF extraction)
- **Backend:** Python FastAPI + `google-genai` SDK + custom **PolicyPipe** module (Gemini Files API + Cached Content for full-doc long-context retrieval; no chunking, no vector DB)
- **DB:** Postgres (audit ledger + cost ledger + `policy_docs` catalog), optional Neo4j if we want to show agent-action provenance graphs (CareGraph pattern)
- **Frontend:** Next.js + Tailwind + shadcn (gas-oracle stack — known good)
- **Infra:** Docker compose for the demo, Vercel + Supabase for the public URL

### PolicyPipe

Gemini-native ingestion + retrieval pipeline for policy documents. Five files (~600 LOC):
- `policy_pipe/extractor.py` — Gemini 2.5 Flash multimodal: PDF → structured sections + auto-tagged domains (`PII`, `financial`, `vendor`, `security`, `export`, `retention`).
- `policy_pipe/catalog.py` — Postgres CRUD on `policy_docs` (`id, name, version, effective_date, superseded_by, gemini_file_id, cache_id, cache_expires_at, domain_tags[], summary, source_sha256`).
- `policy_pipe/cache_builder.py` — Uploads to Gemini Files API; wraps `[file_id, system_prompt]` into `CachedContent` (~75% token cost savings on every escalation). Rebuilds only on policy version bump.
- `policy_pipe/loader.py` — `fetch(domain_tags, role) → list[cache_id]`. Pure SQL lookup, no inference.
- `policy_pipe/refresher.py` — APScheduler cron (every 6h): re-uploads files nearing TTL, atomically swaps `cache_id`.

**Design rationale:**
1. Sentinel deliberately avoids chunking — Pro consumes whole policy docs in 1M context.
2. Direct Gemini Files API + Cached Content usage is visible to sponsor judges (no framework wrapper hiding it).
3. Audit receipts cite exact `policy_version` + `cache_id` — easier to control end-to-end.
4. Minimal deps for a 7-day hackathon build.

Receipt fragment cited from each decision:
```json
"policy_versions_used": [
  {"name": "Data Handling Policy", "version": "v3.2"},
  {"name": "PII Export Standard",  "version": "v1.0"}
],
"gemini_cache_ids": ["cachedContent/abc123", "cachedContent/def456"]
```

### Alternative pitches if Sentinel feels too large
- **`AuditLens`** — same idea but read-only: ingest agent logs from any framework, Gemini long-context analysis produces compliance-grade weekly reports with citations. Smaller scope, still Track 1+2.
- **`PolicyForge`** — Gemini long-context turns a 200-page corporate policy PDF into an executable policy graph that any agent framework can query. Pure Track 2 + Track 4 angle.

---

## Working Notes for Future Sessions

- The user has deep experience in: multi-agent orchestration, healthcare AI, OpenClaw skills, Gemini integration, Arc/Circle nanopayments, RocketRide pipelines.
- The user values: working live demos > slide-ware; defensible technical metrics; reusing patterns across projects.
- Don't invent the gas-oracle stack — `gas-oracle/AGENTS.md` warns Next.js 16 has breaking changes vs. training data; consult `node_modules/next/dist/docs/` before generating code.
- Hackathon submission deliverables: GitHub repo (public), deployed demo URL, video presentation, slide deck, cover image. Plan the video early — winners always have a tight 2-min demo video.
