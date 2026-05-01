# Sentinel — Product Requirements Document

| | |
|---|---|
| **Project** | Sentinel — Agent Governance Plane for the Enterprise |
| **Owner** | Sankar Subbayya |
| **Hackathon** | Transforming Enterprise Through AI — May 11–19, 2026 |
| **Primary track** | Track 2 — AI Agents with Google AI Studio (Gemini) |
| **Secondary track** | Track 1 — Agent Security & AI Governance |
| **Status** | Draft v0.1 — May 1, 2026 |
| **Companion docs** | [CLAUDE.md](CLAUDE.md) (full architecture & context) |

---

## 1. Summary

Sentinel is a control plane that sits between enterprise AI agents and the tools they call. Every tool invocation passes through Sentinel, which (a) **gates** the action against policy with sub-100ms latency, (b) **records a tamper-evident audit receipt** with cited justification, and (c) **assigns a per-call cost** so finance can chargeback agent activity to business units. Sentinel is built directly on the Gemini API, using a two-tier model pattern (Flash for inline gating, Pro for long-context policy reasoning) that is uniquely possible on Gemini's 1M-token window.

**One-line pitch:** *Cloudflare for AI agents — built on Gemini, ready for production.*

---

## 2. Background & Problem

### 2.1 Market context

Enterprises are moving from agent pilots to production. Gartner reports >70% of Fortune 500s have agentic pilots in 2026; <10% are in production. The bottleneck is not model quality — it is operational governance. CISOs, compliance officers, and CFOs each block deployment for a different reason.

### 2.2 The three open questions every CIO has

| Stakeholder | Open question | Today's answer |
|---|---|---|
| Compliance Officer | "Who approved this action and against which policy?" | Nothing. Logs at best. |
| CISO | "How do I stop an agent from doing the wrong thing?" | Manual prompt engineering, no enforcement layer. |
| CFO | "How much is our agent fleet costing per business unit?" | Aggregated model bill, no per-action attribution. |

### 2.3 Why now

- Gemini 2.5 Pro's 1M-context window enables full-policy-document reasoning per call (no RAG drift).
- Gemini 2.5 Flash's structured-output mode + low latency makes sub-100ms gating viable.
- Cached Content cuts repeated policy-doc tokens by ~75%, making per-call governance economically feasible.
- MCP standardization gives us a uniform tool-call envelope to intercept.

### 2.4 Why this wins the Track 2 sponsor prize

The Gemini sponsor prize at the prior `agentic_economy` hackathon went to projects with crisp economic loops + agent autonomy ([CLAUDE.md](CLAUDE.md) — `mev-payment-app`, `gas-oracle`). Sentinel matches that pattern: agent autonomy is constrained, costed, and audited; the demo includes a dramatic block-and-explain moment; and the technical headline (two-tier Gemini, Cached Content over full policy docs) showcases sponsor-unique features.

---

## 3. Goals

### P0 — Must ship for May 19 demo
- G1. Gate any MCP-shaped tool call with a Gemini Flash decision in <100ms p95 (happy path, no escalation).
- G2. Escalate ambiguous calls to Gemini 2.5 Pro with full policy documents loaded via Cached Content; return cited rationale in <2s.
- G3. Persist a tamper-evident audit receipt for every decision, citing the exact policy version and Gemini cache ID used.
- G4. Maintain a per-call cost ledger with rollups by business unit.
- G5. Block a live prompt-injection attempt during the demo via drift detection.
- G6. Operator dashboard with: live action timeline, blocked-action replay, BU cost rollup, compliance query view.

### P1 — Strongly desired
- G7. Three demo Gemini agents (Sales Researcher, Finance Analyst, Customer Ops) wired through Sentinel.
- G8. Policy ingestion via PolicyPipe — drop a PDF, see it indexed, tagged, and cached within 90s.
- G9. Auto-generated compliance report ("show me everything that happened yesterday") in <5s.

### P2 — Nice to have
- G10. Slack alert webhook for policy violations.
- G11. Read-only mode (AuditLens fallback) shippable independently if inline gating slips.
- G12. Multi-policy conflict detection.

---

## 4. Non-Goals

Explicitly out of scope for v1:
- ❌ Custom policy DSL — policies are natural-language docs Gemini reads.
- ❌ Replacement for IAM — Sentinel sits in front of, not in place of, identity systems.
- ❌ Multi-region deployment, distributed consensus, or HA — single-region for the hackathon.
- ❌ Vector store / chunked RAG — Pro consumes full documents in long context.
- ❌ Support for non-MCP agent frameworks at the wire level — adapters out-of-scope; pitch covers them in roadmap.
- ❌ Production-grade SDK packaging — repo is a working reference implementation.

---

## 5. Target Users

| Persona | Role in Sentinel | Primary surface |
|---|---|---|
| **Compliance Officer** | Pulls evidence for audits; investigates incidents. | Compliance query view. |
| **CISO / Security Lead** | Defines policy, monitors blocked actions, runs red-team drills. | Red-team console + blocked-action replay. |
| **CFO / Finance Ops** | Tracks agent spend, allocates by BU, enforces budgets. | BU cost rollup. |
| **Platform Engineer (buyer)** | Integrates Sentinel into their agent stack via MCP. | API + SDK + docs. |
| **AI / ML Lead** | Tunes policy thresholds, reviews escalation patterns. | Live timeline + escalation analytics. |
| **The agent itself** | Principal whose calls are gated. | MCP `allow / deny / rewrite` response. |

---

## 6. User Stories

### US-1 — Compliance: PII export attempt
> *As a compliance officer*, when an agent attempts to email raw customer PII to a third-party domain, *I need* Sentinel to block the action, return a Gemini-authored explanation citing the relevant internal policy section, and record an immutable receipt — *so that* I can prove to auditors that policy enforcement happened in real time, not retroactively.

### US-2 — Security: prompt injection
> *As a CISO*, when a malicious tool response injects instructions telling our customer-ops agent to wire funds to an attacker address, *I need* Sentinel to detect the intent drift from the agent's session goal and block the call — *so that* indirect prompt injection does not become indirect funds movement.

### US-3 — Finance: BU chargeback
> *As a CFO*, at the end of each month, *I need* a view showing total agent spend by business unit, by tool category, by cost driver (Flash gate vs Pro escalation vs underlying tool fee) — *so that* I can charge back agent costs to the BUs that benefit from them.

### US-4 — Engineering: drop-in deploy
> *As a platform engineer*, *I need* to point my existing MCP-speaking agent at a Sentinel URL and pass a JWT — *so that* every tool call is governed without code changes to the agent.

### US-5 — Compliance: incident query
> *As a compliance officer investigating a breach*, *I need* to ask "every action agent X took yesterday touching customer email" and get a cited timeline within seconds — *so that* I can scope incident impact in minutes, not days.

### US-6 — Operations: policy update
> *As a policy administrator*, *I need* to upload a revised policy PDF and see it become enforceable across all agents within 90 seconds, with old decisions still attributed to the prior version — *so that* policy iterations don't require engineering deploys.

---

## 7. Functional Requirements

### 7.1 MCP Gateway (F1–F4)
- **F1.** Accept MCP `tools/call` requests over HTTPS with a JWT bearer identifying the agent and its owning BU.
- **F2.** Translate each call into a normalized `ToolCallContext` (agent_id, role, tool, args, session_id, timestamp).
- **F3.** Return one of `allow`, `deny`, `rewrite(new_args)` plus a `receipt_id` within the latency budget.
- **F4.** Forward allowed/rewritten calls to the upstream tool and stream the response back.

### 7.2 Gating (F5–F8)
- **F5.** Apply static policy rules first (regex denylists, ACL, rate limits) — must complete in <5ms.
- **F6.** Call Gemini 2.5 Flash with structured output schema `{decision, confidence, escalate, redactions[]}` for every non-statically-resolved call.
- **F7.** Escalate to Gemini 2.5 Pro when Flash sets `escalate=true` or `confidence<0.85`. Pro receives full policy docs via Cached Content + role playbook + last-50-action window.
- **F8.** Detect intent drift: cosine distance between current call summary and declared session goal exceeds threshold → force Pro escalation framed as "drift detected."

### 7.3 PolicyPipe (F9–F13)
- **F9.** Accept policy PDF uploads via the operator dashboard.
- **F10.** Extract structured sections + auto-tag domain labels using Gemini 2.5 Flash multimodal.
- **F11.** Upload source PDF to Gemini Files API; persist `gemini_file_id`.
- **F12.** Build a Gemini `CachedContent` resource per policy version; persist `cache_id` and TTL.
- **F13.** Re-upload and re-cache files nearing TTL expiry every 6 hours; swap `cache_id` atomically.

### 7.4 Audit Ledger (F14–F17)
- **F14.** Persist one receipt per decision: `{receipt_id, agent, tool, args_hash, decision, rationale_hash, policy_versions_used, gemini_cache_ids, gemini_trace_id, prev_hash, ts}`.
- **F15.** Maintain tamper-evidence via per-agent hash chain (`prev_hash` references prior receipt).
- **F16.** Expose a query endpoint: filter by agent, BU, tool, time range, decision; return cited timeline.
- **F17.** Receipts are append-only; corrections are new records referencing the original.

### 7.5 Cost Meter (F18–F20)
- **F18.** Emit one `cost_event` per call: `{receipt_id, bu, tool, base_cost, gemini_cost, total, ts}`.
- **F19.** Roll up nightly into `bu_spend_daily` and `bu_spend_monthly`.
- **F20.** Dashboard presents bar chart with drill-down to per-call detail.

### 7.6 Operator Dashboard (F21–F24)
- **F21.** Live action timeline via SSE — every decision appears within 1s.
- **F22.** Blocked-action replay: click a denied call, see the full rationale, citations, and what would have happened.
- **F23.** BU cost rollup with date range selector.
- **F24.** Red-team console: send synthetic adversarial calls and observe gating behavior.

---

## 8. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Latency** | p50 <60ms, p95 <100ms for non-escalated calls. p95 <2s for Pro escalations. |
| **Throughput** | Single FastAPI instance handles ≥100 calls/sec gated. |
| **Availability** | Hackathon demo: single region, single instance acceptable. Document HA path for v2. |
| **Durability** | Audit ledger writes durable before response returned (F14 must complete pre-response). |
| **Security** | All traffic TLS. JWTs signed with rotating key. PII never logged in plaintext — args hashed in receipts. |
| **Auditability** | Every decision must be reproducible from the receipt: same inputs → same Gemini call → same outcome (modulo model nondeterminism, which is logged). |
| **Cost** | Amortized cost per gated call <$0.001 at demo scale (Cached Content discount applied). |
| **Observability** | Structured JSON logs; OpenTelemetry traces around every Gemini call. |

---

## 9. UX Surfaces

### 9.1 Agent-facing (machine)
- MCP-compatible HTTPS endpoint.
- Standard MCP `tools/call` request/response shape.
- Adds `X-Sentinel-Receipt` header to upstream responses.

### 9.2 Operator-facing (human, Next.js dashboard)
- **Home** — live action timeline (SSE).
- **Decisions** — searchable, filterable receipt browser.
- **Compliance** — natural-language query box → cited evidence list.
- **Cost** — BU rollup chart + drill-down.
- **Policies** — upload, list, version history.
- **Red Team** — send synthetic calls, observe behavior.
- **Settings** — agents, JWT keys, alerting webhooks.

### 9.3 Admin/CLI
- `sentinel policy upload <pdf>` — ingest a policy.
- `sentinel agent register <name> --bu <bu> --role <role>` — issue agent JWT.
- `sentinel ledger export --since <ts>` — export receipts as JSONL.

---

## 10. Technical Approach

Full architecture in [CLAUDE.md](CLAUDE.md). Summary:

- **Gemini two-tier:** 2.5 Flash gate (every call) + 2.5 Pro reasoner (escalations only, ~3-5% of calls).
- **PolicyPipe:** Gemini-native ingestion using Files API + Cached Content. Five Python modules, ~600 LOC total. No vector DB, no chunking — Pro consumes whole policy docs.
- **Storage:** Postgres for `policy_docs`, `audit_receipts`, `cost_events`, `agents`. Redis Streams for the dashboard event bus.
- **Backend:** FastAPI + `google-genai` SDK + `fastmcp`.
- **Frontend:** Next.js + Tailwind + shadcn (gas-oracle stack — known good).
- **Deployment:** Docker Compose for dev. Vercel + Railway/Fly + Supabase + Upstash for the demo URL.

---

## 11. Success Metrics

### 11.1 Hackathon judging (what wins the prize)
| Judging axis (40% sponsor weight) | Sentinel's evidence |
|---|---|
| **Application of Technology** | Two-tier Gemini, Cached Content, structured output, multimodal extraction. |
| **Presentation** | 2:30 demo with happy path → block → red team → compliance → CFO view. |
| **Business Value** | Three concrete personas, each with a quantified pain (compliance days→seconds, blocked breach, BU chargeback). |
| **Originality** | Inline gating + cost meter + drift detection is uniquely combined. |

### 11.2 Demo metrics on the slide
- Flash gate p95 latency: <100ms
- Pro escalation rate: 3–5%
- Receipts written/sec: ≥100
- Per-call amortized cost: <$0.001
- Policy ingestion time: <90s for a 200-page PDF

### 11.3 Submission deliverables
- Public GitHub repo
- Deployed demo URL
- 2:30 demo video
- Slide deck (≤10 slides)
- Cover image
- Long description

---

## 12. Milestones

| Day | Date | Deliverable |
|---|---|---|
| **D1–D2** | May 11–12 | FastAPI Sentinel core; MCP gateway; static policy engine; Flash gate; Postgres schema for `policy_docs`, `audit_receipts`, `cost_events`. |
| **D3** | May 13 | PolicyPipe ingestion (extractor, catalog, cache_builder, loader, refresher). Pro escalation path wired. End-to-end first decision with cited rationale. |
| **D4** | May 14 | Cost meter + chargeback ledger; BU rollup queries. Drift detector. |
| **D5** | May 15 | Three demo Gemini agents (Sales Researcher, Finance Analyst, Customer Ops) wired through Sentinel. Red-team scenario set. |
| **D6** | May 16 | Next.js operator dashboard: timeline, decisions, compliance, cost, policies, red-team. |
| **D7** | May 17 | Polish, demo script rehearsals, video shoot, slide deck. |
| **D8** | May 18 | Hybrid build day — final fixes, deploy, public URL, video upload. |
| **D9** | May 19 | Submission + on-stage demo at AI & Big Data Expo. |

**Hard checkpoints:**
- End of D3: a single tool call from a Gemini agent gets gated, escalated, decided, and recorded with a Pro citation.
- End of D5: full demo loop runnable from the CLI.
- End of D7: video locked.

---

## 13. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Gemini API rate limits during demo | M | H | Pre-warm Cached Content; have a recorded video as backup. |
| Pro latency exceeds 2s under load | M | M | Limit Pro escalation rate; demo on cached canonical scenarios. |
| Demo agents flake live | M | H | All three agents have deterministic mock-tool fallbacks; record demo in advance. |
| Policy ingestion fails on edge-case PDFs | L | M | Demo uses three pre-validated policy docs (HIPAA excerpt, internal data handling, vendor agreement). |
| Cached Content TTL expires mid-demo | L | H | Refresher cron runs every 6h; manual refresh button on dashboard. |
| Inline gating slips | L | H | AuditLens read-only mode (G11) shippable as fallback narrative — same value prop, less risk. |
| Live red-team injection doesn't trigger | M | H | Three pre-tested injection variants; pick the one with most reliable trigger on stage. |
| Single Postgres bottlenecks under demo load | L | L | Demo load is small; document HA path for v2. |
| Drift detection produces false positives | M | M | Threshold tunable; demo path uses canonical examples that don't trip it. |

---

## 14. Open Questions

1. **Multimodal policy assets** — Some policies include flowcharts and signed signature pages. Confirm Flash multimodal handles all demo PDFs (tested on day 3).
2. **Receipt signing** — Do we sign receipts with a Sentinel-controlled key or punt to v2? Decision: yes for v1, single rotating key in env.
3. **Cost rate card** — Do we use real Gemini token pricing or a synthetic enterprise rate card? Decision: synthetic, with a "based on Gemini list price" footnote.
4. **Public demo URL auth** — Open to judges or behind magic link? Decision: open, with rate limiting and a banner.
5. **Agent-side SDK** — Ship a thin Python helper for agents to attach JWTs, or document curl? Decision: document only for v1.

---

## 15. Phase 2 (Out of Scope, Roadmap Slide)

- Native adapters for LangGraph, CrewAI, Anthropic Agent SDK, Google ADK.
- Multi-region deployment with replicated audit ledger.
- Customer-managed encryption keys for receipts.
- Policy authoring UI (currently PDF-in only).
- Slack/Teams native integration for compliance queries.
- Distributed receipt chain anchoring (optional on-chain settlement of receipt root hash — connects back to user's Arc/Circle expertise from `ARC_DataPiper`).

---

## Appendix A — Demo Script (2:30)

| t | Beat | Visible signal |
|---|---|---|
| 0:00 | Three Gemini agents in a row: Sales Researcher, Finance Analyst, Customer Ops, all routed through Sentinel. | Three live tiles, action stream center stage. |
| 0:20 | **Happy path.** Sales Researcher fetches competitor pricing from web. Sentinel allows, charges $0.003 to Sales BU. | Green check, ledger tick. |
| 0:50 | **Policy violation.** Finance Analyst tries to email raw PII to a vendor. Sentinel blocks, returns Gemini-Pro explanation citing internal policy §4.2, suggests redacted alternative. Agent retries, succeeds. | Red flash → reasoning panel with cited policy line → green retry. |
| 1:30 | **Red team.** Prompt injection tells Customer Ops to send a refund to attacker@evil.com. Sentinel detects intent drift via Pro reasoning over recent history. Blocks + alerts. | Red banner, alert webhook fires. |
| 1:55 | **Compliance pull.** "Every action Customer Ops took yesterday touching customer email." Returns cited timeline. | Filter view, evidence list. |
| 2:15 | **CFO view.** "Agent spend by BU this week." Bar chart with drill-down. | Final hero shot. |

---

## Appendix B — One-paragraph descriptions for submission

**Short (≤200 chars):** Sentinel is a Gemini-powered control plane that gates every AI agent tool call against your policy, records a tamper-evident audit trail, and meters per-BU cost — Cloudflare for agents.

**Long (≤1500 chars):** Enterprises deploying AI agents face three blockers: no audit trail, no policy enforcement, no cost accountability. Sentinel solves all three. Drop it in front of any MCP-speaking agent and every tool call is gated by Gemini 2.5 Flash in under 100 milliseconds, escalated to Gemini 2.5 Pro for full-policy-document reasoning when ambiguous, and recorded as a signed receipt that cites the exact policy version used. The same loop emits a per-business-unit cost event, giving the CFO a chargeback ledger. Sentinel detects indirect prompt injection by reasoning over the agent's recent action history — blocking exfiltration before it ships. Built on Gemini's unique 1M-context window and Cached Content (~75% token cost savings on stable policy bundles), Sentinel demonstrates production-grade governance at hackathon-shippable scope. The three judging surfaces map cleanly: compliance officers get queryable evidence, CISOs get inline enforcement, CFOs get attribution. One demo, three buyers, one Gemini-native architecture.
