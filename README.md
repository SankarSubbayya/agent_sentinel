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
3. **Recorded** as a signed receipt that cites the exact policy version used
4. **Costed** as a per-business-unit event for chargeback

Agent Sentinel detects indirect prompt injection by reasoning over the agent's recent action history — blocking exfiltration before it ships. Built on Gemini's 1M-context window and Cached Content (~75% token cost savings on stable policy bundles), it demonstrates production-grade governance at hackathon-shippable scope.

> Cloudflare for AI agents. Built on Gemini.

## The three buyers, one demo

- **Compliance officers** get queryable evidence with cited policy versions
- **CISOs** get inline policy enforcement and prompt-injection defense
- **CFOs** get per-BU cost attribution and chargeback

## Why Gemini

Two-tier model usage — exactly what makes Track 2 a Gemini-native story:

- **Gemini 2.5 Flash** — sub-100ms inline gate with structured output, on every call
- **Gemini 2.5 Pro** — long-context policy reasoning over the full policy book (no chunking, no RAG drift) on the ~3-5% of calls that escalate
- **Cached Content** — ~75% token cost savings on stable policy bundles
- **Files API** — authoritative policy storage with multimodal extraction

## Architecture

```
Agent fleet ─MCP─► Sentinel core ─► External tools
                       │
                       ├── Static policy engine (regex/ACL, <5ms)
                       ├── Flash gate (every call, <100ms)
                       ├── Pro reasoner (escalations, full policy docs via Cached Content)
                       ├── Audit ledger (Postgres, content-addressed receipts)
                       └── Cost meter (per-BU, $/call rules)

          Operator dashboard (Next.js) — timeline, replay, BU rollup, red-team console
```

Full architecture: [CLAUDE.md](CLAUDE.md)
Product spec: [PRD.md](PRD.md)

## Demo (2:30)

| t | Beat |
|---|---|
| 0:00 | Three Gemini agents (Sales Researcher, Finance Analyst, Customer Ops) routed through Sentinel |
| 0:20 | **Happy path** — Sales Researcher fetches competitor pricing, allowed, $0.003 charged to Sales BU |
| 0:50 | **Policy violation** — Finance Analyst tries to email raw PII; blocked with cited policy §4.2; agent retries with redaction, succeeds |
| 1:30 | **Red team** — Prompt injection redirects refund to attacker; intent drift detected; blocked + alerted |
| 1:55 | **Compliance pull** — "Every action Customer Ops took yesterday touching customer email" returns cited timeline |
| 2:15 | **CFO view** — Agent spend by BU, drill-down to per-call detail |

## Status

🚧 In active development for May 11–19 hackathon. See [PRD.md](PRD.md) for the build plan.

## License

MIT
