"use client";

import { useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { getPolicies, uploadPolicy, type PolicyDoc } from "@/lib/sentinelApi";

// Placeholder rows until /v1/policies ships.
const PLACEHOLDER: PolicyDoc[] = [
  {
    id: "data-handling-v3.2",
    name: "Data Handling Policy",
    version: "v3.2",
    effective_date: "2025-09-01",
    cache_id: "cachedContent/abc123",
    domain_tags: ["PII", "retention"],
  },
  {
    id: "pii-export-v1.0",
    name: "PII Export Standard",
    version: "v1.0",
    effective_date: "2025-11-15",
    cache_id: "cachedContent/def456",
    domain_tags: ["PII", "export"],
  },
  {
    id: "vendor-comm-v2.1",
    name: "Vendor Communications Policy",
    version: "v2.1",
    effective_date: "2026-02-04",
    cache_id: "cachedContent/ghi789",
    domain_tags: ["vendor", "PII"],
  },
];

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<PolicyDoc[]>(PLACEHOLDER);
  const [usingPlaceholder, setUsingPlaceholder] = useState(true);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    getPolicies()
      .then((res) => {
        if (cancelled) return;
        if (res?.policies?.length) {
          setPolicies(res.policies);
          setUsingPlaceholder(false);
        }
      })
      .catch(() => {
        // backend endpoint not implemented yet — keep placeholders.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploadMsg("uploading...");
    const res = await uploadPolicy(f);
    setUploadMsg(
      res.ok
        ? `uploaded ${f.name}${res.message ? ` — ${res.message}` : ""}`
        : `failed: ${res.message ?? "unknown"}`
    );
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Policy library
          </h1>
          <p className="text-sm text-muted-foreground">
            Long-context policy docs cached in Gemini Files API. Cited from
            every Pro-tier decision.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.md,.txt"
            onChange={onUpload}
            className="hidden"
          />
          <Button onClick={() => fileRef.current?.click()}>
            Upload policy
          </Button>
        </div>
      </div>

      {usingPlaceholder && (
        <Card className="border-amber-500/40 bg-amber-500/5">
          <CardContent className="pt-4 text-xs text-amber-300">
            Showing placeholder rows — backend endpoint{" "}
            <span className="mono">/v1/policies</span> not yet wired.
          </CardContent>
        </Card>
      )}

      {uploadMsg && (
        <Card>
          <CardContent className="pt-4 text-xs mono">{uploadMsg}</CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Policies</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Effective</TableHead>
                <TableHead>Cache ID</TableHead>
                <TableHead>Tags</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {policies.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell className="mono text-xs">{p.version}</TableCell>
                  <TableCell className="mono text-xs">
                    {p.effective_date}
                  </TableCell>
                  <TableCell className="mono text-xs text-muted-foreground">
                    {p.cache_id || "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {(p.domain_tags ?? []).map((t) => (
                        <Badge key={t} variant="secondary" className="text-xs">
                          {t}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
