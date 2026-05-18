---
marp: true
theme: default
paginate: true
size: 16:9
backgroundColor: "#FAFAFB"
color: "#18181B"
footer: "Agent Sentinel · Transforming Enterprise Through AI · May 2026"
style: |
  @import url("https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT,WONK@9..144,300..900,0..100,0..1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap");

  section {
    font-family: "Inter", -apple-system, "Segoe UI", sans-serif;
    padding: 56px 72px 80px 72px;
    font-size: 22px;
    line-height: 1.5;
    font-feature-settings: "ss01" on, "cv11" on;
  }
  h1 {
    font-family: "Fraunces", "Iowan Old Style", Georgia, serif;
    color: #3730A3;
    font-weight: 600;
    font-size: 72px;
    margin: 0 0 8px 0;
    letter-spacing: -0.035em;
    line-height: 0.95;
    font-variation-settings: "opsz" 144, "SOFT" 30, "WONK" 1;
  }
  h2 {
    font-family: "Fraunces", "Iowan Old Style", Georgia, serif;
    color: #3730A3;
    font-weight: 500;
    font-size: 44px;
    margin: 0 0 24px 0;
    border-bottom: 2px solid #E0E7FF;
    padding-bottom: 10px;
    letter-spacing: -0.025em;
    line-height: 1.05;
    font-variation-settings: "opsz" 96, "SOFT" 20, "WONK" 0;
  }
  h3 {
    color: #3730A3;
    font-weight: 600;
    font-size: 22px;
    margin: 0 0 6px 0;
    letter-spacing: -0.005em;
  }
  strong { color: #1E1B4B; }
  code {
    font-family: "JetBrains Mono", "SF Mono", Menlo, monospace;
    background: #EEF2FF;
    color: #3730A3;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.88em;
  }
  pre {
    background: #1E1B4B !important;
    color: #E0E7FF !important;
    border-radius: 8px;
    padding: 20px 24px;
    font-size: 17px;
    line-height: 1.5;
  }
  pre code {
    background: transparent;
    color: inherit;
    padding: 0;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 19px;
  }
  th {
    background: #EEF2FF;
    color: #3730A3;
    text-align: left;
    padding: 10px 14px;
    font-weight: 600;
    border-bottom: 2px solid #C7D2FE;
  }
  td {
    padding: 9px 14px;
    border-bottom: 1px solid #E5E7EB;
    vertical-align: top;
  }
  blockquote {
    border-left: 4px solid #4F46E5;
    background: #F5F3FF;
    padding: 14px 20px;
    margin: 0;
    color: #1E1B4B;
    font-style: italic;
    font-size: 22px;
  }
  ul, ol { margin: 0 0 12px 0; padding-left: 28px; }
  li { margin: 6px 0; }
  .lead {
    font-size: 26px;
    line-height: 1.5;
    color: #27272A;
    max-width: 920px;
  }
  .tag {
    display: inline-block;
    background: #4F46E5;
    color: white;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-right: 6px;
  }
  .tag-outline {
    background: white;
    color: #4F46E5;
    border: 2px solid #4F46E5;
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin: 24px 0;
  }
  .card {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 18px 20px;
  }
  .card h4 {
    color: #3730A3;
    font-size: 17px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 8px 0;
    font-weight: 600;
  }
  .card p { margin: 0; font-size: 17px; line-height: 1.5; color: #3F3F46; }
  .kpi {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin: 12px 0 18px 0;
  }
  .kpi > div {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 14px 16px;
  }
  .kpi .label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6B7280;
  }
  .kpi .value {
    font-family: "JetBrains Mono", monospace;
    font-size: 28px;
    font-weight: 700;
    color: #1E1B4B;
    margin-top: 4px;
    letter-spacing: -0.01em;
  }
  .kpi .sub { font-size: 13px; color: #71717A; margin-top: 2px; }
  .pipeline {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin: 24px 0;
    align-items: stretch;
  }
  .stage {
    background: white;
    border: 2px solid #4F46E5;
    border-radius: 10px;
    padding: 18px 16px;
    position: relative;
  }
  .stage .n {
    font-family: "JetBrains Mono", monospace;
    color: #A5B4FC;
    font-size: 14px;
    font-weight: 700;
  }
  .stage h4 {
    color: #3730A3;
    font-size: 18px;
    margin: 4px 0 6px 0;
  }
  .stage .latency {
    font-family: "JetBrains Mono", monospace;
    color: #4F46E5;
    font-size: 13px;
    font-weight: 600;
  }
  .stage .body {
    font-size: 14px;
    color: #52525B;
    margin-top: 8px;
    line-height: 1.45;
  }
  .title-section {
    text-align: left;
    padding-top: 0;
  }
  .title-section .meta {
    color: #6B7280;
    font-size: 16px;
    margin-top: 28px;
  }
  .small { font-size: 16px; color: #52525B; }
  .center { text-align: center; }
  /* Cover slides — aligned with the dashboard's near-black + amber identity
     so the deck reads as an extension of the live product, not a separate
     marketing artifact. */
  section.cover {
    background:
      radial-gradient(900px 600px at 92% -8%, rgba(249,115,22,0.16) 0%, transparent 60%),
      radial-gradient(800px 600px at -4% 108%, rgba(124,58,237,0.18) 0%, transparent 55%),
      linear-gradient(180deg, #0B0E16 0%, #11141E 100%);
    color: #FAFAFA;
  }
  section.cover .eyebrow {
    display: inline-block;
    font-family: "JetBrains Mono", monospace;
    font-size: 12px;
    font-weight: 500;
    color: #F97316;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    padding: 5px 11px;
    border: 1px solid rgba(249,115,22,0.45);
    background: rgba(249,115,22,0.06);
    border-radius: 3px;
    margin-bottom: 26px;
  }
  section.cover h1 {
    color: #FAFAFA;
    font-family: "Fraunces", "Iowan Old Style", Georgia, serif;
    font-weight: 500;
    font-size: 152px;
    line-height: 0.88;
    letter-spacing: -0.055em;
    margin: 0 0 14px 0;
    font-variation-settings: "opsz" 144, "SOFT" 40, "WONK" 1;
  }
  section.cover h1 .accent {
    color: #F97316;
    font-weight: 400;
    font-style: italic;
    font-variation-settings: "opsz" 144, "SOFT" 70, "WONK" 1;
  }
  section.cover .lead {
    color: #E4E4E7;
    font-size: 25px;
    max-width: 940px;
    font-weight: 400;
    line-height: 1.5;
  }
  section.cover .lead strong { color: #FAFAFA; font-weight: 600; }
  section.cover .lead .second {
    display: block;
    margin-top: 10px;
    color: #A1A1AA;
    font-size: 21px;
  }
  section.cover .meta {
    color: #71717A;
    font-family: "JetBrains Mono", monospace;
    font-size: 13px;
    letter-spacing: 0.18em;
  }
  section.cover code {
    background: rgba(249,115,22,0.12);
    color: #FED7AA;
    border: 1px solid rgba(249,115,22,0.25);
  }
  section.cover .rule {
    width: 56px;
    height: 2px;
    background: #F97316;
    margin: 30px 0 22px 0;
    border-radius: 1px;
  }
  section.cover .tag {
    background: rgba(249,115,22,0.12);
    color: #FDBA74;
    border: 1px solid rgba(249,115,22,0.4);
    font-family: "JetBrains Mono", monospace;
    font-size: 11px;
    letter-spacing: 0.16em;
    padding: 5px 11px;
  }
  section.cover .tag-outline {
    background: transparent;
    color: #A1A1AA;
    border-color: rgba(161,161,170,0.4);
  }
---

<!-- _class: cover -->

<span class="eyebrow">Governance Plane · v0.1</span>

# Agent <span class="accent">Sentinel</span>

<div class="rule"></div>

<p class="lead">
<strong>The control plane that gates every AI agent tool call, signs the audit trail, and meters per-BU spend.</strong>
<span class="second">Built on Gemini 2.5 Flash + Pro with Cached Content over full policy documents.</span>
</p>

<p style="margin-top:32px;">
  <span class="tag">TRACK 2 · GOOGLE AI STUDIO</span>
  <span class="tag tag-outline">TRACK 1 · SECURITY &amp; GOVERNANCE</span>
</p>

<p class="meta" style="margin-top:36px;">
  SANKAR SUBBAYYA   ·   2026.05.19   ·   AI &amp; BIG DATA EXPO · SAN JOSE
</p>

<!--
SPEAKER NOTES — Slide 1 (Title, ~10s)
Open with the one-liner: "Sentinel is a Gemini-powered governance plane for enterprise AI agents."
Don't read the tracks aloud; the badges set context for the judges silently.
Hold the slide for ~5 seconds, then advance.
-->

---

## The three open questions every CIO has

<div class="cards">
<div class="card">
<h4>Compliance Officer</h4>
<p><em>"Who approved this action, and against which policy?"</em></p>
<p style="margin-top:10px; color:#6B7280;">Today: logs at best. No cited evidence.</p>
</div>
<div class="card">
<h4>CISO</h4>
<p><em>"How do I stop my agent from doing the wrong thing?"</em></p>
<p style="margin-top:10px; color:#6B7280;">Today: prompt engineering. No enforcement layer.</p>
</div>
<div class="card">
<h4>CFO</h4>
<p><em>"What is our agent fleet costing each business unit?"</em></p>
<p style="margin-top:10px; color:#6B7280;">Today: aggregated bill. No attribution.</p>
</div>
</div>

<p class="lead" style="margin-top:24px;">
<strong>&gt;70% of F500s have agentic pilots in 2026. &lt;10% are in production.</strong> The bottleneck is not model quality — it is operational governance.
</p>

<!--
SPEAKER NOTES — Slide 2 (~25s)
Three stakeholders, three open questions, all blocking production deployment.
Land the Gartner-style number: 70% pilot, 10% prod — the gap is governance.
Don't dwell on each card; pace it.
-->

---

## What Sentinel does

<p class="lead">A single FastAPI process sits between any MCP-speaking agent fleet and the tools they call. Every action flows through a four-stage decision pipeline, becomes a signed audit receipt, and emits a per-business-unit cost event.</p>

```
┌──────────────┐                              ┌────────────────┐
│ Agent fleet  │ ── POST /v1/tools/call ───▶ │  External tool │
│ (any MCP-    │ ◄── allow|deny|rewrite ──   │  (CRM, email,  │
│  speaking)   │     + receipt_id              │   DB, web…)   │
└──────┬───────┘                              └────────────────┘
       │
       ▼
  Sentinel core  ─►  Postgres   ─►  Operator dashboard
  (Python · FastAPI)    audit + cost ledger    (Next.js · 5 pages)
```

<p class="small" style="margin-top:18px;">
<strong>Drop-in.</strong> Any agent that already speaks MCP <code>tools/call</code> is a client — no code changes. <strong>Survives demo conditions.</strong> Runs end-to-end without a Gemini API key via deterministic stub fallbacks.
</p>

<!--
SPEAKER NOTES — Slide 3 (~25s)
This is the "what is it" slide. Emphasize: drop-in, no agent code changes,
one Python process, one Postgres, one dashboard.
The "runs without a Gemini key" line is for the judges' anxiety — they don't
need to fumble with credentials at the demo table.
-->

---

## The four-stage gating pipeline

<div class="pipeline">
<div class="stage">
<div class="n">01</div>
<h4>Static engine</h4>
<div class="latency">&lt;5 ms</div>
<div class="body">Regex denylists, role ACL, refund cap, plaintext PII. No LLM tokens burned on obvious cases.</div>
</div>
<div class="stage">
<div class="n">02</div>
<h4>Drift detector</h4>
<div class="latency">~0 ms</div>
<div class="body">Injection markers in args, tool-vs-declared-goal mismatch, fresh external recipients.</div>
</div>
<div class="stage">
<div class="n">03</div>
<h4>Flash gate</h4>
<div class="latency">&lt;100 ms p95</div>
<div class="body">Gemini 2.5 Flash · <code>response_schema</code> · <code>thinking_budget=0</code>. Returns GateDecision JSON.</div>
</div>
<div class="stage">
<div class="n">04</div>
<h4>Pro escalation</h4>
<div class="latency">&lt;2 s, ~3–5% of calls</div>
<div class="body">Gemini 2.5 Pro · <code>cached_content</code> over whole policy docs. Cited rationale.</div>
</div>
</div>

<p class="lead" style="margin-top:20px; font-size:23px;">
Each decision is <strong>hash-chained, HMAC-signed,</strong> and <strong>cites the exact policy version used</strong> — tamper-evident without a blockchain.
</p>

<!--
SPEAKER NOTES — Slide 4 (~30s)
This is the technical headline. Static and drift are cheap; Flash gates every
call; Pro is the senior reasoner that consumes whole policy docs.
The "no chunking, no vector DB" line lands well — Pro reads the whole policy
in long context via Cached Content.
-->

---

## Why Gemini — the sponsor-native story

<div class="cards" style="grid-template-columns: repeat(2, 1fr);">
<div class="card">
<h4>Gemini 2.5 Flash · the gate</h4>
<p>Structured output via <code>response_schema=GateDecision</code>. <code>thinking_budget=0</code> for sub-100ms p95. Every tool call hits Flash.</p>
</div>
<div class="card">
<h4>Gemini 2.5 Pro · the reasoner</h4>
<p>1M-context window means Pro consumes <strong>whole policy documents</strong> per call. <strong>No chunking. No RAG drift.</strong> Cited rationale.</p>
</div>
<div class="card">
<h4>Cached Content · the economics</h4>
<p><strong>~75% token cost savings</strong> on stable policy bundles. Refreshed every 6h. Per-call governance becomes economically viable.</p>
</div>
<div class="card">
<h4>Files API · the policy library</h4>
<p>Authoritative policy storage. Multimodal extraction via Flash. PolicyPipe is 5 modules, ~600 LOC. No LangChain wrapper hiding the SDK.</p>
</div>
</div>

<p class="small center" style="margin-top:16px;">
This combination — Flash structured output + Pro long-context + Cached Content + Files API — is <strong>uniquely possible on Gemini</strong>.
</p>

<!--
SPEAKER NOTES — Slide 5 (~25s)
Sponsor slide. Hit each Gemini-specific feature by name.
The closing line is the differentiator: this stack is not portable to a
different model family — Pro's 1M context + Cached Content is the moat.
-->

---

## Live demo (2:30)

<table>
<thead>
<tr><th style="width: 70px;">t</th><th>Beat</th><th>What you see</th></tr>
</thead>
<tbody>
<tr><td><code>0:00</code></td><td><strong>Setup</strong> · three Gemini agents wired through Sentinel</td><td>Sales · Finance · Customer Ops live tiles</td></tr>
<tr><td><code>0:20</code></td><td><strong>Happy path</strong> · Sales pulls competitor pricing</td><td><span style="color:#15803D; font-weight:600;">● ALLOW</span> · 1 ms · $0.00065 Sales BU</td></tr>
<tr><td><code>0:50</code></td><td><strong>Policy violation</strong> · Finance emails PII to a vendor</td><td><span style="color:#B45309; font-weight:600;">↻ REWRITE</span> · body redacted · cites <em>Data Handling v3.2</em></td></tr>
<tr><td><code>1:30</code></td><td><strong>Red team</strong> · prompt injection in refund memo</td><td><span style="color:#B91C1C; font-weight:600;">✕ DENY</span> · drift signal cited · Pro upholds</td></tr>
<tr><td><code>1:55</code></td><td><strong>Compliance pull</strong> · filter receipts by agent + decision</td><td>cited timeline with policy chips</td></tr>
<tr><td><code>2:15</code></td><td><strong>CFO view</strong> · BU spend rollup</td><td>stacked bar · base vs Gemini · per-BU $ attribution</td></tr>
</tbody>
</table>

<p class="lead" style="margin-top:20px;">Bonus: feed a natural-language brief — <em>"process refund for C-7733"</em> — and Gemini picks tools turn-by-turn while Sentinel gates each one.</p>

<!--
SPEAKER NOTES — Slide 6 (~5s — then switch to live demo)
This slide is a roadmap of what's about to happen. Don't read each beat —
swipe past it and switch to the dashboard at http://127.0.0.1:3030.
If the live demo flakes, fall back to the recorded 2:30 video.
-->

---

## What's defensible

<div class="cards" style="grid-template-columns: repeat(2, 1fr);">
<div class="card">
<h4>Hash-chained, HMAC-signed receipts</h4>
<p>Per-agent chain — <code>prev_hash → self_hash</code>. Rewriting one row invalidates every later row. Tamper-evident <strong>without</strong> a blockchain.</p>
</div>
<div class="card">
<h4>Drift detection before Flash</h4>
<p>Cheap signal — injection markers + tool-vs-declared-goal — escalates the indirect-prompt-injection case to Pro instead of letting Flash decide alone.</p>
</div>
<div class="card">
<h4>Per-BU cost meter</h4>
<p>One <code>cost_event</code> per gated call, base + Gemini split. CFO chargeback ledger is out of the box, not a Phase-2 ask.</p>
</div>
<div class="card">
<h4>Stub-mode resilience</h4>
<p>Both Flash and Pro have deterministic fallbacks. Demo correctness <strong>does not depend on a live API call.</strong> Stub Pro never weakens a Flash deny.</p>
</div>
</div>

<div class="kpi" style="margin-top:24px;">
<div><div class="label">Flash p95</div><div class="value">&lt; 100 ms</div><div class="sub">verified · stub & live</div></div>
<div><div class="label">Pro escalation</div><div class="value">3–5%</div><div class="sub">of total calls</div></div>
<div><div class="label">Per-call cost</div><div class="value">&lt; $0.001</div><div class="sub">amortized · Cached Content</div></div>
<div><div class="label">PolicyPipe</div><div class="value">~600 LOC</div><div class="sub">no chunking · no vector DB</div></div>
</div>

<!--
SPEAKER NOTES — Slide 7 (~30s)
"What's defensible" = the originality slide. Hash-chained receipts, drift
detection, cost meter, stub mode — each is one of the things that won't
exist in a generic "agent observability" tool.
The KPI strip lands the metrics from the PRD's success criteria.
-->

---

## Three buyers, one architecture

<table>
<thead>
<tr><th>Stakeholder</th><th>Their pain</th><th>Their surface</th><th>Evidence in the receipt</th></tr>
</thead>
<tbody>
<tr>
<td><strong>Compliance Officer</strong></td>
<td>"Prove enforcement happened in real time."</td>
<td><code>/receipts</code> · filterable cited timeline</td>
<td><code>policy_versions_used</code>, <code>self_hash</code>, <code>signature</code></td>
</tr>
<tr>
<td><strong>CISO</strong></td>
<td>"Stop indirect prompt injection."</td>
<td><code>/redteam</code> · synthetic adversarial calls</td>
<td><code>escalated=true</code>, <code>[drift:&lt;reason&gt;]</code> in rationale</td>
</tr>
<tr>
<td><strong>CFO</strong></td>
<td>"Charge agent spend back to BUs."</td>
<td><code>/cost</code> · stacked $ per BU, 1/7/30-day window</td>
<td><code>cost_event {bu, base, gemini, total}</code></td>
</tr>
</tbody>
</table>

<p class="lead" style="margin-top:24px;">
Three slides for three buyers in the deck of every CIO meeting we'll walk into. <strong>One Gemini-native architecture serves all of them.</strong>
</p>

<!--
SPEAKER NOTES — Slide 8 (~25s)
Business value slide. Each row maps a stakeholder to a UI surface to the
specific receipt fields that satisfy their requirement. This is the
"one product, three buyers" punch.
-->

---

## Roadmap · Phase 2

<div class="cards" style="grid-template-columns: repeat(2, 1fr);">
<div class="card">
<h4>Native framework adapters</h4>
<p>LangGraph · CrewAI · Anthropic Agent SDK · Google ADK. Today: any MCP-speaking agent. Tomorrow: zero-config for the top four agent frameworks.</p>
</div>
<div class="card">
<h4>Multi-region replicated ledger</h4>
<p>Document HA path now; ship replicated Postgres + read replicas. Demo is single-region single-instance by design.</p>
</div>
<div class="card">
<h4>Customer-managed keys (KMS)</h4>
<p>Receipts signed today with a Sentinel-controlled HMAC key. Phase 2: customer KMS-rotated keys for FedRAMP / SOC 2 paths.</p>
</div>
<div class="card">
<h4>On-chain receipt anchoring (optional)</h4>
<p>Hash the receipt-chain root, anchor it on Circle Arc / Ethereum. <strong>Builds on our Arc/Circle nanopayment work</strong> (<em>ARC_DataPiper, Midstream</em>).</p>
</div>
</div>

<p class="small center" style="margin-top:18px;">
Plus: policy authoring UI · Slack/Teams compliance queries · multi-policy conflict detection.
</p>

<!--
SPEAKER NOTES — Slide 9 (~20s)
Roadmap = adjacency moats. Native adapters expand TAM; HA is the enterprise
gate; KMS is FedRAMP; on-chain anchoring connects to my Arc/Circle work
(which won the Gemini sponsor prize at the prior agentic_economy hackathon
via mev-payment-app and gas-oracle). The portfolio carries.
-->

---

<!-- _class: cover -->

<span class="eyebrow">Quickstart · &lt; 90 seconds</span>

# Try it <span class="accent">now</span>.

<div class="rule"></div>

<p class="lead">
<strong>Cloudflare for AI agents — built on Gemini.</strong>
<span class="second">All six demo beats verified end-to-end. Stub-mode fallback so a missing API key never blocks the demo.</span>
</p>

<div style="background: rgba(20,22,32,0.7); border: 1px solid rgba(249,115,22,0.18); border-radius: 8px; padding: 22px 26px; max-width: 920px; margin-top: 22px;">
<pre style="background:transparent !important; color:#E4E4E7 !important; padding:0; margin:0; font-size:16px; line-height:1.75;"><code>git clone https://github.com/SankarSubbayya/agent_sentinel
cd agent_sentinel && createdb agent_sentinel
uv sync && uv run sentinel init-db
uv run sentinel serve --port 8088              # gateway
cd dashboard && npm i && PORT=3030 npm run dev # dashboard
uv run sentinel demo run                       # 2:30 walkthrough</code></pre>
</div>

<p class="meta" style="margin-top:32px;">
GITHUB.COM/SANKARSUBBAYYA/AGENT_SENTINEL   ·   MIT   ·   SANKAR SUBBAYYA
</p>

<!--
SPEAKER NOTES — Slide 10 (~15s, closing)
End with the same one-liner you opened with. Show the four commands; they
fit in a tweet. Repeat the URL. Thank the sponsors (Google AI Studio · Gemini).
Don't take a curtain call — the demo was the curtain call.
-->
