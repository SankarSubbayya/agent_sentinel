"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn, fmtUsd } from "@/lib/utils";
import { getCostRollup, type CostRow } from "@/lib/sentinelApi";

const RANGES = [1, 7, 30] as const;

export default function SpendPage() {
  const [days, setDays] = useState<(typeof RANGES)[number]>(7);
  const [rows, setRows] = useState<CostRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getCostRollup(days);
      setRows(res.rows);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  const total = rows.reduce((acc, r) => acc + r.total_usd, 0);
  const totalCalls = rows.reduce((a, r) => a + r.calls, 0);
  const totalGemini = rows.reduce((a, r) => a + r.gemini_usd, 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            per business unit · chargeback
          </div>
          <h1 className="mt-1 text-[22px] font-semibold leading-none">Spend</h1>
        </div>
        <div className="flex items-center gap-1 rounded-md border border-border/70 bg-card/50 p-0.5 text-[11px]">
          {RANGES.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "rounded-sm px-2.5 py-1 transition-colors",
                d === days
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Headline numbers — inline, no card-in-card */}
      <div className="grid grid-cols-3 gap-3 border-y border-border/60 py-4">
        <Headline
          label="Total spend"
          value={fmtUsd(total)}
          sub={`across ${rows.length || 0} BU${rows.length === 1 ? "" : "s"}`}
        />
        <Headline
          label="Gated calls"
          value={totalCalls.toLocaleString()}
          sub={`window ${days}d`}
        />
        <Headline
          label="Gemini share"
          value={total > 0 ? `${((totalGemini / total) * 100).toFixed(0)}%` : "—"}
          sub={`${fmtUsd(totalGemini)} of total`}
        />
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="panel">
          <div className="panel-header">
            <div>
              <span className="font-medium text-foreground">$ per BU</span>
              <span className="ml-2 text-muted-foreground/70">
                stacked · base call vs Gemini reasoning
              </span>
            </div>
            <div className="text-[10px] text-muted-foreground/70">
              {loading ? "refreshing…" : `${days}-day window`}
            </div>
          </div>
          <div className="h-[360px] px-2 py-3">
            {rows.length === 0 ? (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                no spend recorded in window
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows} barCategoryGap={36}>
                  <CartesianGrid
                    strokeDasharray="2 4"
                    stroke="hsl(220 10% 18%)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="bu"
                    tick={{ fill: "hsl(220 8% 60%)", fontSize: 11 }}
                    axisLine={{ stroke: "hsl(220 10% 18%)" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "hsl(220 8% 60%)", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `$${v.toFixed(4)}`}
                  />
                  <Tooltip
                    cursor={{ fill: "hsl(28 95% 56% / 0.06)" }}
                    contentStyle={{
                      background: "hsl(220 14% 8%)",
                      border: "1px solid hsl(220 10% 18%)",
                      borderRadius: 6,
                      fontSize: 12,
                      fontVariantNumeric: "tabular-nums",
                    }}
                    labelStyle={{ color: "hsl(0 0% 96%)" }}
                  />
                  <Bar
                    dataKey="base_usd"
                    stackId="a"
                    fill="hsl(28 95% 56%)"
                    name="base"
                    radius={[0, 0, 2, 2]}
                  />
                  <Bar
                    dataKey="gemini_usd"
                    stackId="a"
                    fill="hsl(195 80% 55%)"
                    name="gemini"
                    radius={[2, 2, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Right-side detail table */}
        <div className="panel">
          <div className="panel-header">
            <span className="font-medium text-foreground">Breakdown</span>
            <span className="text-muted-foreground/70">per BU</span>
          </div>
          <table className="w-full text-[12px]">
            <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
              <tr className="border-b border-border/60">
                <th className="px-3 py-2 text-left font-medium">BU</th>
                <th className="px-3 py-2 text-right font-medium">Calls</th>
                <th className="px-3 py-2 text-right font-medium">Base</th>
                <th className="px-3 py-2 text-right font-medium">Gemini</th>
                <th className="px-3 py-2 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-xs text-muted-foreground">
                    no spend in window
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.bu} className="hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{r.bu}</td>
                  <td className="px-3 py-2 mono text-right text-muted-foreground">
                    {r.calls.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 mono text-right">{fmtUsd(r.base_usd)}</td>
                  <td className="px-3 py-2 mono text-right text-sky-300/90">
                    {fmtUsd(r.gemini_usd)}
                  </td>
                  <td className="px-3 py-2 mono text-right font-medium">
                    {fmtUsd(r.total_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-[11px] italic text-muted-foreground/80">
        synthetic rate card · based on Gemini 2.5 list price. Plug in invoice-grade
        billing before production.
      </p>
    </div>
  );
}

function Headline({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 mono text-2xl font-semibold leading-none">{value}</div>
      {sub && (
        <div className="mt-1 text-[11px] text-muted-foreground/80">{sub}</div>
      )}
    </div>
  );
}
