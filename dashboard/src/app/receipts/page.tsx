"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
} from "@/components/ui/drawer";
import { DecisionBadge } from "@/components/decision-badge";
import { buColor, relativeTime } from "@/lib/utils";
import {
  getReceipts,
  type Decision,
  type Receipt,
  type ReceiptsFilter,
} from "@/lib/sentinelApi";

const DECISIONS: Array<Decision | ""> = ["", "allow", "deny", "rewrite"];

export default function ReceiptsPage() {
  const [filter, setFilter] = useState<ReceiptsFilter>({ limit: 100 });
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

  // Client-side date filter (backend doesn't expose date range yet).
  const filtered = useMemo(() => {
    return receipts.filter((r) => {
      const t = new Date(r.created_at).getTime();
      if (from && t < new Date(from).getTime()) return false;
      if (to && t > new Date(to).getTime()) return false;
      return true;
    });
  }, [receipts, from, to]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          Decision browser
        </h1>
        <p className="text-sm text-muted-foreground">
          Filter, drill into a receipt, see policy citations.
        </p>
      </div>

      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 pt-4 md:grid-cols-6">
          <Input
            placeholder="agent_id"
            value={filter.agent_id ?? ""}
            onChange={(e) =>
              setFilter((f) => ({ ...f, agent_id: e.target.value }))
            }
          />
          <Input
            placeholder="bu"
            value={filter.bu ?? ""}
            onChange={(e) => setFilter((f) => ({ ...f, bu: e.target.value }))}
          />
          <Input
            placeholder="tool"
            value={filter.tool ?? ""}
            onChange={(e) =>
              setFilter((f) => ({ ...f, tool: e.target.value }))
            }
          />
          <select
            value={filter.decision ?? ""}
            onChange={(e) =>
              setFilter((f) => ({
                ...f,
                decision: e.target.value as Decision | "",
              }))
            }
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
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
          />
          <Input
            type="datetime-local"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            title="to"
          />
        </CardContent>
        <div className="flex justify-end border-t px-4 py-3">
          <Button size="sm" onClick={load} disabled={loading}>
            {loading ? "loading..." : "Apply"}
          </Button>
        </div>
      </Card>

      {error && (
        <Card className="border-destructive/40">
          <CardContent className="pt-4 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>BU</TableHead>
                <TableHead>Tool</TableHead>
                <TableHead>Decision</TableHead>
                <TableHead>By</TableHead>
                <TableHead className="text-right">Latency</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="py-6 text-center text-sm text-muted-foreground"
                  >
                    no rows
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((r) => (
                  <TableRow
                    key={r.receipt_id}
                    className="cursor-pointer"
                    onClick={() => setSelected(r)}
                  >
                    <TableCell className="mono text-xs">
                      {relativeTime(r.created_at)}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs mono ${buColor(
                          r.bu || r.agent_id
                        )}`}
                      >
                        {r.agent_id}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">{r.bu}</TableCell>
                    <TableCell className="mono text-xs">{r.tool}</TableCell>
                    <TableCell>
                      <DecisionBadge decision={r.decision} />
                    </TableCell>
                    <TableCell>
                      <Badge variant="info" className="lowercase">
                        {r.decided_by}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right mono text-xs">
                      {r.latency_ms}ms
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Drawer
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DrawerContent>
          {selected && (
            <>
              <DrawerHeader>
                <DrawerTitle className="flex items-center gap-2">
                  Receipt
                  <DecisionBadge decision={selected.decision} />
                  {selected.escalated && (
                    <Badge variant="rewrite">escalated</Badge>
                  )}
                </DrawerTitle>
                <DrawerDescription className="mono text-xs">
                  {selected.receipt_id}
                </DrawerDescription>
              </DrawerHeader>

              <div className="space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="agent_id" value={selected.agent_id} />
                  <Field label="bu" value={selected.bu} />
                  <Field label="tool" value={selected.tool} />
                  <Field label="decided_by" value={selected.decided_by} />
                  <Field
                    label="latency_ms"
                    value={`${selected.latency_ms}ms`}
                  />
                  <Field
                    label="created_at"
                    value={selected.created_at}
                  />
                </div>

                <div>
                  <div className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                    Rationale
                  </div>
                  <div className="rounded-md border bg-muted/30 p-3 text-sm leading-relaxed">
                    {selected.rationale || "(none)"}
                  </div>
                </div>

                <div>
                  <div className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                    Policy versions used
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(selected.policy_versions_used ?? []).length === 0 ? (
                      <span className="text-xs text-muted-foreground">
                        (none cited)
                      </span>
                    ) : (
                      selected.policy_versions_used!.map((p, i) => (
                        <Badge
                          key={i}
                          variant="secondary"
                          className="mono text-xs"
                        >
                          {p.name} · {p.version}
                        </Badge>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mono text-xs break-all">{value}</div>
    </div>
  );
}
