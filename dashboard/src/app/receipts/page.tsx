"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from "@/components/ui/drawer";
import { DecisionBadge, TierPill } from "@/components/decision-badge";
import { cn, clockTime, compactAgent, relativeTime } from "@/lib/utils";
import {
  getReceipts,
  type Decision,
  type Receipt,
  type ReceiptsFilter,
} from "@/lib/sentinelApi";

const DECISIONS: Array<Decision | ""> = ["", "allow", "deny", "rewrite"];

export default function ReceiptsPage() {
  const [filter, setFilter] = useState<ReceiptsFilter>({ limit: 200 });
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Receipt | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getReceipts(filter);
      setReceipts(res.receipts);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    return receipts.filter((r) => {
      const t = new Date(r.created_at).getTime();
      if (from && t < new Date(from).getTime()) return false;
      if (to && t > new Date(to).getTime()) return false;
      return true;
    });
  }, [receipts, from, to]);

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            audit ledger · hash-chained
          </div>
          <h1 className="mt-1 text-[22px] font-semibold leading-none">Receipts</h1>
        </div>
        <div className="mono text-[11px] text-muted-foreground">
          {filtered.length}/{receipts.length}
        </div>
      </div>

      {/* Inline filter strip — no nested-card chrome */}
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-border/70 bg-card/40 p-2">
        <FilterInput
          placeholder="agent_id"
          value={filter.agent_id ?? ""}
          onChange={(v) => setFilter((f) => ({ ...f, agent_id: v }))}
        />
        <FilterInput
          placeholder="bu"
          value={filter.bu ?? ""}
          onChange={(v) => setFilter((f) => ({ ...f, bu: v }))}
        />
        <FilterInput
          placeholder="tool"
          value={filter.tool ?? ""}
          onChange={(v) => setFilter((f) => ({ ...f, tool: v }))}
        />
        <select
          value={filter.decision ?? ""}
          onChange={(e) =>
            setFilter((f) => ({
              ...f,
              decision: e.target.value as Decision | "",
            }))
          }
          className="h-7 rounded-sm border border-border/70 bg-background px-2 text-[12px]"
        >
          {DECISIONS.map((d) => (
            <option key={d} value={d}>
              {d || "any decision"}
            </option>
          ))}
        </select>
        <Input
          type="datetime-local"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          title="from"
          className="h-7 w-[180px] text-[12px]"
        />
        <Input
          type="datetime-local"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          title="to"
          className="h-7 w-[180px] text-[12px]"
        />
        <Button
          size="sm"
          onClick={load}
          disabled={loading}
          className="ml-auto h-7 text-[12px]"
        >
          {loading ? "loading…" : "Apply"}
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      <div className="panel">
        <table className="w-full text-[12px]">
          <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border/60 bg-card/40">
              <th className="px-3 py-2 text-left font-medium">Time</th>
              <th className="px-3 py-2 text-left font-medium">Agent</th>
              <th className="px-3 py-2 text-left font-medium">Tool</th>
              <th className="px-3 py-2 text-left font-medium">Decision</th>
              <th className="px-3 py-2 text-left font-medium">Tier</th>
              <th className="px-3 py-2 text-right font-medium">Latency</th>
              <th className="px-3 py-2 text-left font-medium">Rationale</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-xs text-muted-foreground">
                  no receipts match
                </td>
              </tr>
            ) : (
              filtered.map((r) => (
                <tr
                  key={r.receipt_id}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-muted/30",
                    selected?.receipt_id === r.receipt_id && "bg-primary/5"
                  )}
                  onClick={() => setSelected(r)}
                >
                  <td className="px-3 py-2 mono text-muted-foreground">
                    <div>{clockTime(r.created_at)}</div>
                    <div className="text-[10px] text-muted-foreground/70">
                      {relativeTime(r.created_at)}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium">{compactAgent(r.agent_id)}</div>
                    <div className="text-[10px] text-muted-foreground/80">
                      {r.bu}
                    </div>
                  </td>
                  <td className="px-3 py-2 mono">{r.tool}</td>
                  <td className="px-3 py-2">
                    <DecisionBadge decision={r.decision} />
                  </td>
                  <td className="px-3 py-2">
                    <TierPill tier={r.decided_by as "static" | "flash" | "pro"} />
                  </td>
                  <td className="px-3 py-2 mono text-right">
                    {r.latency_ms}
                    <span className="ml-0.5 text-[10px] text-muted-foreground/70">
                      ms
                    </span>
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    <span className="line-clamp-1 leading-snug">
                      {r.rationale}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Drawer
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DrawerContent>
          {selected && (
            <>
              <DrawerHeader>
                <DrawerTitle className="flex flex-wrap items-center gap-2">
                  <DecisionBadge decision={selected.decision} />
                  <TierPill tier={selected.decided_by as "static" | "flash" | "pro"} />
                  <span className="text-sm font-medium">{selected.tool}</span>
                  {selected.escalated && (
                    <span className="rounded-sm border border-amber-500/40 bg-amber-500/10 px-1.5 text-[10px] uppercase tracking-wide text-amber-300">
                      escalated
                    </span>
                  )}
                </DrawerTitle>
                <DrawerDescription className="mono text-[11px] text-muted-foreground">
                  {selected.receipt_id}
                </DrawerDescription>
              </DrawerHeader>

              <div className="space-y-5 text-sm">
                <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-[12px]">
                  <Field label="agent_id" value={selected.agent_id} />
                  <Field label="bu" value={selected.bu ?? "—"} />
                  <Field label="tool" value={selected.tool} />
                  <Field label="decided_by" value={selected.decided_by} />
                  <Field label="latency" value={`${selected.latency_ms}ms`} />
                  <Field label="created_at" value={selected.created_at} />
                </div>

                <Section title="Rationale">
                  <div className="rounded-md border border-border/60 bg-muted/30 p-3 leading-relaxed">
                    {selected.rationale || "(none)"}
                  </div>
                </Section>

                <Section title="Policy versions cited">
                  {(selected.policy_versions_used ?? []).length === 0 ? (
                    <span className="text-xs text-muted-foreground">
                      (none — decision did not consult cached policy)
                    </span>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {selected.policy_versions_used!.map((p, i) => (
                        <span
                          key={i}
                          className="rounded-sm border border-border/60 bg-card/60 px-2 py-0.5 mono text-[11px]"
                        >
                          {p.name} · {p.version}
                        </span>
                      ))}
                    </div>
                  )}
                </Section>
              </div>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

function FilterInput({
  placeholder,
  value,
  onChange,
}: {
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Input
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-7 w-[140px] text-[12px] mono"
    />
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 mono text-[12px] break-all">{value}</div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {title}
      </div>
      {children}
    </div>
  );
}
