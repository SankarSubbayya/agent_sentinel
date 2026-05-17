# Sentinel Dashboard

Next.js 14 + Tailwind + shadcn/ui operator console for the Agent Sentinel
governance plane.

## Prereqs

- Node 18.18+ (Next 14.2 minimum)
- The Sentinel FastAPI backend running locally on `http://127.0.0.1:8088`

## Run

```bash
cd dashboard
cp .env.local.example .env.local        # or set NEXT_PUBLIC_SENTINEL_URL
npm install
npm run dev                              # http://localhost:3000
```

For a production build:

```bash
npm run build && npm start
```

## Pages

- `/` Live action timeline (polls `/v1/receipts` every 2s)
- `/receipts` Filterable decision browser + side drawer
- `/cost` BU spend rollup with stacked bars (recharts)
- `/redteam` Hand-craft tool calls; 4 demo presets
- `/policies` Policy library + upload (placeholder rows until `/v1/policies` ships)

## Notes

- Pinned to **Next.js 14.2.18**. Do NOT bump to 15/16 without revisiting.
- Polling on `/` is structured so swapping to SSE `EventSource` is a
  one-line change in `src/app/page.tsx`.
- shadcn/ui primitives are hand-vendored under `src/components/ui/` (no
  `dlx shadcn` step required).
