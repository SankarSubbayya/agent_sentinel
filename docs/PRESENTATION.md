# Presentation — viewing and exporting

The deck source is [`/presentation.md`](../presentation.md) in **Marp** format. Marp is markdown with slide breaks (`---`) and inline `<style>` — readable as plain text, renders as 10 slides.

## View the slides

**Easiest — VS Code preview**
1. Install the **Marp for VS Code** extension (id: `marp-team.marp-vscode`)
2. Open `presentation.md`
3. Cmd-Shift-V — preview pane shows the deck live
4. The Marp icon in the editor toolbar lets you export

**Browser preview (no install)**
```bash
npx @marp-team/marp-cli --server presentation.md
# opens http://localhost:8080
```

## Export

```bash
# Install Marp CLI once
npm i -g @marp-team/marp-cli

# PDF (good for sharing / submission upload)
marp presentation.md --pdf -o sentinel.pdf

# PPTX (good if a judge asks for editable slides)
marp presentation.md --pptx -o sentinel.pptx

# Standalone HTML (good for embed / Vercel)
marp presentation.md --html -o sentinel.html

# PNG/JPG of each slide (good for individual images on a submission form)
marp presentation.md --images png
```

## Speaker notes

Every slide has a `<!-- ... -->` block at the bottom with notes — pacing, what to say, what to skip. Marp surfaces these in presenter mode (`marp --preview --bespoke`).

## Customizing

The deck uses an inline `<style>` block at the top of `presentation.md` so it's self-contained — no external CSS, no theme files. To tweak colors, edit the variables there:

| What | Where |
|---|---|
| Accent (deep indigo) | `#3730A3` / `#4F46E5` |
| Page background | `#FAFAFB` |
| Cover-slide gradient | `linear-gradient(135deg, #312E81 0%, #4F46E5 100%)` |
| Body font | `Inter` |
| Headline font | `Playfair Display` (serif) |
| Mono font | `JetBrains Mono` |

## Slide map (10 slides)

| # | Title | Notes |
|---|---|---|
| 1 | Agent Sentinel (cover) | Title + tagline + track badges. ~10s. |
| 2 | The three open questions every CIO has | Compliance / CISO / CFO pain points. ~25s. |
| 3 | What Sentinel does | Diagram + drop-in pitch. ~25s. |
| 4 | The four-stage gating pipeline | Static → Drift → Flash → Pro. ~30s. |
| 5 | Why Gemini | Sponsor-native features. ~25s. |
| 6 | Live demo (2:30) | Slide is a roadmap; swipe past, switch to dashboard. ~5s. |
| 7 | What's defensible | Hash-chained receipts, drift, cost meter, stub mode + KPIs. ~30s. |
| 8 | Three buyers, one architecture | Business value table. ~25s. |
| 9 | Roadmap — Phase 2 | Adapters, HA, KMS, on-chain anchoring. ~20s. |
| 10 | Try it. Now. (cover) | Quickstart + repo URL. ~15s. |

**Total: ~3:00 with live demo embedded after slide 6.**

Submission spec says ≤10 slides — this hits exactly 10.
