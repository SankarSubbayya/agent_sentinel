"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getPolicies, uploadPolicy, type PolicyDoc } from "@/lib/sentinelApi";

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<PolicyDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadMsg, setUploadMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function reload() {
    setLoading(true);
    try {
      const res = await getPolicies();
      setPolicies(res?.policies ?? []);
    } catch {
      setPolicies([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploadMsg({ ok: true, text: `uploading ${f.name}…` });
    const res = await uploadPolicy(f);
    setUploadMsg({
      ok: res.ok,
      text: res.ok
        ? `ingested ${f.name}${res.message ? ` · ${res.message}` : ""}`
        : `failed: ${res.message ?? "unknown"}`,
    });
    if (fileRef.current) fileRef.current.value = "";
    if (res.ok) reload();
  }

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            policy library · cached for Pro reasoning
          </div>
          <h1 className="mt-1 text-[22px] font-semibold leading-none">Policies</h1>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.md,.txt"
            onChange={onUpload}
            className="hidden"
          />
          <Button
            onClick={() => fileRef.current?.click()}
            className="h-8 text-[12px]"
          >
            + Ingest policy PDF
          </Button>
        </div>
      </div>

      {uploadMsg && (
        <div
          className={cn(
            "rounded-md border px-3 py-2 text-[12px] mono",
            uploadMsg.ok
              ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
              : "border-destructive/40 bg-destructive/5 text-destructive"
          )}
        >
          {uploadMsg.text}
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="font-medium text-foreground">Indexed policies</span>
          <span className="text-muted-foreground/70">
            {loading ? "loading…" : `${policies.length} active`}
          </span>
        </div>
        <table className="w-full text-[12px]">
          <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border/60 bg-card/40">
              <th className="px-3 py-2 text-left font-medium">Name</th>
              <th className="px-3 py-2 text-left font-medium">Version</th>
              <th className="px-3 py-2 text-left font-medium">Effective</th>
              <th className="px-3 py-2 text-left font-medium">Tags</th>
              <th className="px-3 py-2 text-left font-medium">Cache</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {policies.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-8 text-center text-xs text-muted-foreground">
                  {loading ? (
                    "loading…"
                  ) : (
                    <span>
                      no policies ingested · run{" "}
                      <code className="mono rounded-sm bg-muted/60 px-1.5 py-0.5">
                        uv run sentinel policy upload demo_policies/*.pdf
                      </code>
                    </span>
                  )}
                </td>
              </tr>
            ) : (
              policies.map((p) => (
                <tr key={p.id} className="hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{p.name}</td>
                  <td className="px-3 py-2 mono text-muted-foreground">{p.version}</td>
                  <td className="px-3 py-2 mono text-[11px] text-muted-foreground">
                    {p.effective_date ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(p.domain_tags ?? []).map((t) => (
                        <span
                          key={t}
                          className="rounded-sm border border-border/60 bg-card/60 px-1.5 mono text-[10px]"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 mono text-[11px] text-muted-foreground">
                    {p.cache_id ? (
                      <span title={p.cache_id}>
                        {p.cache_id.replace(/^cachedContents\//, "")}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
