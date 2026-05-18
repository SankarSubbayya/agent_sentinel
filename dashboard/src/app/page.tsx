"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn, clockTime, compactAgent, fmtUsd, relativeTime } from "@/lib/utils";
import { DecisionBadge, TierPill } from "@/components/decision-badge";
import { getReceipts, type Receipt } from "@/lib/sentinelApi";

const POLL_MS = 2000;
const TIMELINE_LIMIT = 500;

interface Kpis {
  total: number;
  denyRate: number;
  rewriteRate: number;
  p50: number;
  p95: number;
  spendTotal: number;
}

function computeKpis(rows: Receipt[]): Kpis {
  if (rows.length === 0) {
    return { total: 0, denyRate: 0, rewriteRate: 0, p50: 0, p95: 0, spendTotal: 0 };
  }
  const lat = [...rows.map((r) => r.latency_ms)].sort((a, b) => a - b);
  const p = (q: number) => lat[Math.min(lat.length - 1, Math.floor(q * lat.length))];
  const denies = rows.filter((r) => r.decision === "deny").length;
  const rewrites = rows.filter((r) => r.decision === "rewrite").length;
  return {
    total: rows.length,
    denyRate: denies / rows.length,
    rewriteRate: rewrites / rows.length,
    p50: p(0.5),
    p95: p(0.95),
    spendTotal: 0, // wired by /v1/cost/rollup if we want; out of scope for the timeline.
  };
}

export default function ActivityPage() {
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const seen = useRef<Set<string>>(new Set());
  const [flash, setFlash] = useState<Set<string>>(new Set());

  const tick = useCallback(async () => {
    try {
      const res = await getReceipts({ limit: TIMELINE_LIMIT });
      setError(null);
      const fresh = new Set<string>();
      for (const r of res.receipts) {
        if (!seen.current.has(r.receipt_id)) fresh.add(r.receipt_id);
      }
      if (fresh.size > 0) {
        setFlash(fresh);
        fresh.forEach((id) => seen.current.add(id));
        setTimeout(() => setFlash(new Set()), 1500);
      }
      res.receipts.forEach((r) => seen.current.add(r.receipt_id));
      setReceipts(res.receipts);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    tick();
    if (paused) return;
    const id = setInterval(tick, POLL_MS);
    return () => clearInterval(id);
  }, [tick, paused]);

  const kpis = useMemo(() => computeKpis(receipts), [receipts]);

  return (
    <div className="space-y-5">
      {/* Page heading + live indicator */}
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            governance plane · live
          </div>
          <h1 className="mt-1 text-[22px] font-semibold leading-none">
            Activity
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                paused ? "bg-zinc-500" : "bg-emerald-400 animate-pulse"
              )}
            />
            {paused ? "paused" : `polling ${POLL_MS / 1000}s`}
          </span>
          <button
            onClick={() => setPaused((p) => !p)}
            className="rounded-sm border border-border/70 bg-card/60 px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
          >
            {paused ? "Resume" : "Pause"}
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <KpiTile
          label="Decisions (recent window)"
          value={kpis.total.toLocaleString()}
          sub={`last ${TIMELINE_LIMIT} receipts`}
        />
        <KpiTile
          label="Deny rate"
          value={`${(kpis.denyRate * 100).toFixed(1)}%`}
          sub={`${(kpis.rewriteRate * 100).toFixed(1)}% rewritten`}
          tone={kpis.denyRate > 0.1 ? "warn" : "ok"}
        />
        <KpiTile
          label="Latency p95"
          value={`${kpis.p95}ms`}
          sub={`p50 ${kpis.p50}ms`}
          tone={kpis.p95 > 100 ? "warn" : "ok"}
        />
        <KpiTile
          label="Demo cost band"
          value={fmtUsd(0.0001 * kpis.total)}
          sub="synthetic · Gemini list price"
        />
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          Sentinel unreachable — {error}
        </div>
      )}

      {/* Decision table */}
      <div className="panel">
        <div className="panel-header">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="font-medium text-foreground">Decisions</span>
            <span className="text-muted-foreground/70">
              · gated tool calls in arrival order
            </span>
          </div>
          <div className="mono text-[10px] text-muted-foreground/80">
            {receipts.length}/{TIMELINE_LIMIT}
          </div>
        </div>
        {receipts.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="max-h-[640px] overflow-auto">
            <table className="w-full text-[12px]">
              <thead className="sticky top-0 z-10 bg-card/95 text-[10px] uppercase tracking-wider text-muted-foreground backdrop-blur">
                <tr className="border-b border-border/60">
                  <Th className="w-[88px]">Time</Th>
                  <Th className="w-[120px]">Agent</Th>
                  <Th className="w-[180px]">Tool</Th>
                  <Th className="w-[100px]">Decision</Th>
                  <Th className="w-[56px]">Tier</Th>
                  <Th className="w-[72px] text-right">Latency</Th>
                  <Th>Rationale</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {receipts.map((r) => (
                  <tr
                    key={r.receipt_id}
                    className={cn(
                      "transition-colors hover:bg-muted/30",
                      flash.has(r.receipt_id) && "bg-primary/10"
                    )}
                  >
                    <Td className="mono text-muted-foreground">
                      <div title={r.created_at}>{clockTime(r.created_at)}</div>
                      <div className="text-[10px] text-muted-foreground/70">
                        {relativeTime(r.created_at)}
                      </div>
                    </Td>
                    <Td>
                      <div className="font-medium">{compactAgent(r.agent_id)}</div>
                      <div className="text-[10px] text-muted-foreground/80">
                        {r.bu}
                      </div>
                    </Td>
                    <Td className="mono">{r.tool}</Td>
                    <Td>
                      <DecisionBadge decision={r.decision} />
                    </Td>
                    <Td>
                      <TierPill tier={r.decided_by as "static" | "flash" | "pro"} />
                      {r.escalated && (
                        <div className="mt-1 text-[9px] uppercase tracking-wide text-amber-400/80">
                          escalated
                        </div>
                      )}
                    </Td>
                    <Td className="mono text-right tabular-nums">
                      {r.latency_ms}
                      <span className="ml-0.5 text-[10px] text-muted-foreground/70">
                        ms
                      </span>
                    </Td>
                    <Td className="text-muted-foreground">
                      <span className="line-clamp-2 leading-snug">
                        {r.rationale}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Th({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <th
      className={cn(
        "px-3 py-2 text-left font-medium tracking-wider",
        className
      )}
    >
      {children}
    </th>
  );
}

function Td({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <td className={cn("px-3 py-2 align-top", className)}>{children}</td>
  );
}

function KpiTile({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "ok" | "warn" | "neutral";
}) {
  const accent =
    tone === "warn"
      ? "text-amber-300"
      : tone === "ok"
        ? "text-emerald-300"
        : "text-foreground";
  return (
    <div className="kpi-tile">
      <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </div>
      <div className={cn("mt-1 mono text-2xl font-semibold leading-none", accent)}>
        {value}
      </div>
      {sub && (
        <div className="mt-1 text-[11px] text-muted-foreground/80">{sub}</div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="p-10 text-center">
      <div className="mx-auto mb-2 inline-flex h-8 w-8 items-center justify-center rounded-md border border-dashed border-border text-muted-foreground">
        ·
      </div>
      <div className="text-sm text-muted-foreground">
        No decisions yet.{" "}
        <a href="/redteam" className="text-primary hover:underline">
          Open the red-team console
        </a>{" "}
        or run{" "}
        <code className="mono rounded-sm bg-muted/60 px-1.5 py-0.5 text-[11px]">
          uv run sentinel demo run
        </code>
        .
      </div>
    </div>
  );
}
