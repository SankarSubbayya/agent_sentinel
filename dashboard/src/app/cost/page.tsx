"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getCostRollup, type CostRow } from "@/lib/sentinelApi";

const RANGES = [1, 7, 30] as const;

export default function CostPage() {
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

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            BU spend rollup
          </h1>
          <p className="text-sm text-muted-foreground">
            Per-business-unit chargeback. Base call cost vs Gemini reasoning
            cost, stacked.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {RANGES.map((d) => (
            <Button
              key={d}
              size="sm"
              variant={d === days ? "default" : "outline"}
              onClick={() => setDays(d)}
            >
              {d}d
            </Button>
          ))}
        </div>
      </div>

      {error && (
        <Card className="border-destructive/40">
          <CardContent className="pt-4 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-xs uppercase text-muted-foreground">
              Total spend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold mono">
              ${total.toFixed(4)}
            </div>
            <div className="text-xs text-muted-foreground">
              across {rows.length} BU{rows.length === 1 ? "" : "s"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-xs uppercase text-muted-foreground">
              Calls
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold mono">
              {rows.reduce((a, r) => a + r.calls, 0).toLocaleString()}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-xs uppercase text-muted-foreground">
              Window
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold mono">last {days}d</div>
            <Badge variant="secondary" className="mt-1">
              {loading ? "refreshing..." : "live"}
            </Badge>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-sm">$ per BU (stacked)</CardTitle>
        </CardHeader>
        <CardContent className="h-[360px] pt-4">
          {rows.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              no data
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(var(--border))"
                />
                <XAxis dataKey="bu" stroke="hsl(var(--muted-foreground))" />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar
                  dataKey="base_usd"
                  stackId="a"
                  fill="hsl(173 80% 45%)"
                  name="base"
                />
                <Bar
                  dataKey="gemini_usd"
                  stackId="a"
                  fill="hsl(280 70% 60%)"
                  name="gemini"
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <p className="text-xs italic text-muted-foreground">
        synthetic rate card based on Gemini list price — replace with
        invoice-grade billing before production.
      </p>
    </div>
  );
}
