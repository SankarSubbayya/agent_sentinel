"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DecisionBadge } from "@/components/decision-badge";
import { buColor, cn, relativeTime } from "@/lib/utils";
import { getReceipts, type Receipt } from "@/lib/sentinelApi";

const POLL_MS = 2000;

export default function TimelinePage() {
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const seen = useRef<Set<string>>(new Set());
  const [flash, setFlash] = useState<Set<string>>(new Set());

  const tick = useCallback(async () => {
    try {
      const res = await getReceipts({ limit: 50 });
      setError(null);
      const fresh = new Set<string>();
      for (const r of res.receipts) {
        if (!seen.current.has(r.receipt_id)) {
          fresh.add(r.receipt_id);
        }
      }
      if (fresh.size > 0) {
        setFlash(fresh);
        fresh.forEach((id) => seen.current.add(id));
        // Clear flash after the animation duration
        setTimeout(() => setFlash(new Set()), 1500);
      }
      res.receipts.forEach((r) => seen.current.add(r.receipt_id));
      setReceipts(res.receipts);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // NOTE: structured so swapping to EventSource is a one-line change:
  //   const es = new EventSource(`${SENTINEL_URL}/v1/events/stream`);
  //   es.onmessage = (ev) => upsert(JSON.parse(ev.data) as Receipt);
  useEffect(() => {
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => clearInterval(id);
  }, [tick]);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Live action timeline
          </h1>
          <p className="text-sm text-muted-foreground">
            Every gated tool call from the Sentinel control plane. Polling
            every {POLL_MS / 1000}s.
          </p>
        </div>
        <Badge variant="secondary">{receipts.length} recent</Badge>
      </div>

      {error && (
        <Card className="border-destructive/40">
          <CardContent className="pt-4 text-sm text-destructive">
            Couldn&apos;t reach Sentinel at{" "}
            <span className="mono">{error}</span>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Decisions</CardTitle>
          <CardDescription>
            allow / deny / rewrite, with Gemini rationale and decided-by tier.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {receipts.length === 0 ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              No receipts yet. Hit the red-team console to generate some.
            </div>
          ) : (
            <ul className="divide-y divide-border/60">
              {receipts.map((r) => (
                <li
                  key={r.receipt_id}
                  className={cn(
                    "flex items-start gap-3 px-4 py-3 text-sm",
                    flash.has(r.receipt_id) && "animate-flash-row"
                  )}
                >
                  <div className="w-20 shrink-0 text-xs text-muted-foreground mono">
                    {relativeTime(r.created_at)}
                  </div>
                  <span
                    className={cn(
                      "inline-flex shrink-0 items-center rounded-md border px-2 py-0.5 text-xs font-medium mono",
                      buColor(r.bu || r.agent_id)
                    )}
                  >
                    {r.agent_id}
                  </span>
                  <span className="shrink-0 mono text-xs">{r.tool}</span>
                  <DecisionBadge decision={r.decision} />
                  <span className="shrink-0 text-xs text-muted-foreground mono">
                    {r.latency_ms}ms
                  </span>
                  <Badge variant="info" className="shrink-0 lowercase">
                    {r.decided_by}
                  </Badge>
                  {r.escalated && (
                    <Badge variant="rewrite" className="shrink-0">
                      escalated
                    </Badge>
                  )}
                  <span className="ml-1 line-clamp-2 text-muted-foreground">
                    {r.rationale}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
