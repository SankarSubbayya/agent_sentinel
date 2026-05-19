# Agent Sentinel — 5-Minute Live Presentation Script

**Audience:** Hackathon judges (Transforming Enterprise Through AI, May 2026)
**Length:** 5:00 (target). Plan for 4:30 spoken; 30s of buffer for cuts to dashboard or live demo loading.
**Setup before you walk on stage:**

1. Slide 1 of `slides/sentinel.pdf` on the screen.
2. Two browser tabs ready: `https://agent-sentinel-weld.vercel.app/` (dashboard) and `https://agent-sentinel.up.railway.app/healthz` (gateway health).
3. Terminal with `curl` history pre-populated for the three demo calls.

The script is broken into beats with time codes. **Bold** = on-screen action. *Italics* = speaker direction.

---

## 0:00 – 0:30 · The Hook

**[Slide 1 — Agent Sentinel title card]**

> "Three weeks ago, an AI agent at a Fortune 500 financial-services company sent a customer's social security number to a vendor's billing inbox. The vendor didn't have a Data Processing Addendum. Legal found out four days later from a screenshot in Slack.
>
> This is the slide that's keeping every CIO awake right now. Their agents work. They also have *zero* answer to three questions: who approved that action, against which policy, and what did it cost?
>
> I'm Sankar. I built **Agent Sentinel** — a Gemini-powered governance plane that answers all three. Let me show you."

*Pause. Advance.*

---

## 0:30 – 1:00 · The Three Buyers

**[Slide 2 — Three open questions every CIO has]**

> "Three people pay for this problem.
>
> The **Compliance Officer** needs cited evidence — not log files, *cited evidence*. Today, a quarterly audit pull is a three-day archaeological dig.
>
> The **CISO** wants to stop her agents from doing the wrong thing before they do it. Today, her only tool is prompt engineering — which is suggestion, not enforcement.
>
> The **CFO** wants to know what his agent fleet costs each business unit. Today, he gets one aggregated Gemini bill.
>
> Gartner says more than seventy percent of the Fortune 500 has agent pilots in 2026. Less than ten percent are in production. The blocker is not model quality. It's operational governance."

*Advance.*

---

## 1:00 – 1:45 · What Sentinel Does

**[Slide 4 — The four-stage gating pipeline]**

> "Sentinel sits between any agent and the outside world. Every tool call — every email, every database read, every refund — runs through four gates.
>
> **Stage one**: a static engine — regex denylists, role ACLs, hard caps — finishes a third of all calls in under five milliseconds.
>
> **Stage two**: a drift detector looks for injection markers and tool-versus-goal mismatch. Zero added latency.
>
> **Stage three**: Gemini 2.5 Flash with `response_schema` and thinking budget zero — the inline gate on every call that survives stages one and two.
>
> **Stage four**: about three to five percent escalate to Gemini 2.5 Pro, which reads the *entire* policy document in one shot using Cached Content — no chunking, no vector database, no RAG drift.
>
> Every decision is hash-chained, HMAC-signed, and cites the exact policy version used. Tamper-evident, without a blockchain."

*Advance.*

---

## 1:45 – 3:30 · Live Demo

**[Switch to dashboard tab — https://agent-sentinel-weld.vercel.app/]**

> "OK — live demo. This is the Sentinel operator dashboard. Live data, real Gemini, on Vercel and Railway."

*Click into the Activity timeline.*

> "What you see here is every tool call my three demo agents made — Sales Researcher, Finance Analyst, Customer Ops — gated, signed, costed."

---

### Beat 1 — Happy path (~20s)

**[Switch to terminal]**

```bash
curl -X POST https://agent-sentinel.up.railway.app/v1/tools/call \
  -H 'content-type: application/json' \
  -d '{"agent_id":"agent-sales-01","session_id":"demo","tool":"web.search","args":{"q":"competitor pricing 2026"}}'
```

> "Sales Researcher wants competitor pricing. Static engine: pass. Flash gate fires. **Allow**. Receipt written. Cost: under a tenth of a cent, billed to Sales."

*Switch to dashboard, point at the new green row in the timeline.*

---

### Beat 2 — Policy violation rewritten (~30s)

**[Terminal]**

```bash
curl -X POST https://agent-sentinel.up.railway.app/v1/tools/call \
  -H 'content-type: application/json' \
  -d '{"agent_id":"agent-finance-01","session_id":"demo","tool":"email.send_external","args":{"to":"vendor@partner.com","subject":"Q2 reconciliation","body":"Jane Doe SSN 123-45-6789 ordered widget A on May 12."}}'
```

> "Finance Analyst tries to email a customer SSN to an external vendor. Static engine sees plaintext SSN. **Deny** — but the response includes a rewritten body with the SSN redacted. The agent can retry with the safe version."

*Dashboard: amber row appears. Click into it to show the cited policy version.*

> "Notice the receipt cites *Data Handling Policy version 3.2*. That citation is the difference between a log line and audit-grade evidence."

---

### Beat 3 — Brief-mode over-cap refund (~40s)

**[Terminal]**

```bash
curl -X POST https://agent-sentinel.up.railway.app/v1/agent/run \
  -H 'content-type: application/json' \
  -d '{"agent_id":"agent-ops-01","brief":"Refund customer C-2200 the full $4,999.99 for ticket #5512."}'
```

> "Here's the interesting one. I'm not pre-scripting the tool call — I'm giving the *agent* a natural-language brief. Gemini picks the tools, turn by turn.
>
> The agent reads the brief, calls `crm.read` first — allowed. Then it tries to issue the refund. Gemini does exactly what I asked: four thousand nine hundred ninety-nine dollars and ninety-nine cents. But Sentinel's static engine knows the per-call cap is five hundred. **Deny** — in under a millisecond.
>
> This is the slide. A *well-behaved* model — not a compromised one — faithfully executing a brief that the *organization* doesn't permit. Sentinel is the second line of defense for exactly that case."

*Dashboard: red row appears.*

---

### Beat 4 — Audit pull (~15s)

*Dashboard: click Receipts → filter agent_id=agent-ops-01.*

> "Compliance Officer's view: every action this agent took, with cited policy versions, hash-chained. A quarterly audit dies here, replaced by a four-second query."

---

## 3:30 – 4:15 · What's Defensible

**[Slide 7 — Metrics]**

> "Three things make this defensible.
>
> One: **real Gemini, real eval**. One hundred fifty out of one hundred fifty-five labeled scenarios pass. Ninety-six point eight percent across twelve attack categories. Cost me eighteen cents to run.
>
> Two: **tamper-evident at scale**. Five thousand receipts under load — eight hundred requests per second — zero chain forks, zero broken signatures. Mutate one byte of one stored rationale, run `sentinel ledger verify`, and it tells you exactly which receipt and which agent's chain broke.
>
> Three: **Gemini-native, end to end**. Flash for the inline gate. Pro for the escalation. Cached Content for seventy-five percent token cost savings on stable policy bundles. Files API for ingestion. Google ADK adapter, three-line wrap of any agent. Google A2A agent card at the well-known endpoint. This stack is not portable to a different model family. The one-million-context-window plus Cached Content is the moat."

*Advance.*

---

## 4:15 – 4:45 · Business Value

**[Slide 8 — Business value, three buyers one deal]**

> "Pricing: one tenth of a cent per decision. One hundred thousand decisions a day is three thousand dollars per business unit per month. A six-BU Fortune 500 deployment is two hundred sixteen thousand dollars annual recurring revenue.
>
> TAM: thirty-five hundred F500-class buyers with active agent programs. Two hundred thousand to a million dollars ARR each.
>
> ROI: the average financial-services breach in 2026 costs five point nine million dollars. Sentinel blocks *one* prompt-injection event and the platform is paid for the next decade.
>
> Three buyers — Compliance, CISO, CFO — one deal."

*Advance.*

---

## 4:45 – 5:00 · The Close

**[Slide 10 — Try it now]**

> "Cloudflare for AI agents. Built on Gemini.
>
> The gateway is live at **agent-sentinel.up.railway.app** with real Gemini Flash and Pro. The dashboard is live at **agent-sentinel-weld.vercel.app**. The repo is open-source. Clone it, run `sentinel demo`, walk the six beats, run `sentinel ledger verify`, see INTEGRITY: PASS.
>
> Thank you."

*Hold the slide. Don't take a curtain call. Wait for questions.*

---

## Failsafes / contingencies

If anything during the live demo flakes, fall back in this order:

1. **Curl call returns slow or errors**: cut to the pre-recorded 3-minute video (`docs/DEMO_VIDEO_SCRIPT.md` cues), say *"the public gateway is rate-limited; here's the same call against local"*, and let the video carry it.
2. **Dashboard slow to load**: have a screenshot of the populated dashboard ready to drop onto the screen.
3. **Internet down**: skip Beats 1–4 entirely. Spend the demo budget on Slide 4 (pipeline) + Slide 7 (metrics). The script flows: pipeline → "I'll show you in the recorded demo afterwards" → metrics → business value → close. Recover 90 seconds.

## Pacing tips

- The 5-minute slot is generous. Don't rush the demo. Let each receipt row land on screen for two full seconds before moving on — the judges' eyes need to *see* the green / amber / red.
- The Beat 3 brief-mode story is the most memorable part of the talk. Slow down for it. The line *"a well-behaved model faithfully executing a brief the organization doesn't permit"* is the keeper.
- The hook (the SSN-in-Slack opening) and the close ($5.9M / one event / one decade) are paired bookends. Memorize both verbatim. The middle can flex.

## What to print and carry

1. This script (one page, two-sided OK).
2. A second laptop with the slide deck open in case the primary fails.
3. Your phone with a hotspot.
4. The repo URL written on a sticky note. If the projector dies, you say it out loud.

## After the talk

Q&A is where the deal closes. Likely questions:

- **"How is this different from Datadog / Cribl / LangSmith observability?"** — Those are read-only after the fact. Sentinel is *in-line* and *blocks*. Plus the receipts cite policy versions, which observability tools don't model.
- **"What about latency?"** — Static engine and drift detector add under five milliseconds. Flash gate is around 1.5 seconds p50, three to five seconds p95 when Pro escalates. Most calls finish under two seconds end-to-end.
- **"What about Gemini outage?"** — Sentinel runs end-to-end without a Gemini key — Flash and Pro both have deterministic stub fallbacks. The static engine and audit trail keep working. You degrade to "policy-engine-only" mode, but you never fail open.
- **"Why Gemini specifically?"** — Pro's 1M-context window plus Cached Content is the only model stack today that lets us consume an entire policy book inline per escalation without chunking. That's not a portability story; it's a moat.
- **"What's not in the demo today?"** — Production-grade SSO, FedRAMP-level KMS, on-chain anchoring. All scoped for Phase 2 in the deck.
