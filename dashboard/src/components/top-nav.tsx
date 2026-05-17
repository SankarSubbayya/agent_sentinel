"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { healthcheck } from "@/lib/sentinelApi";

const links = [
  { href: "/", label: "Timeline" },
  { href: "/receipts", label: "Receipts" },
  { href: "/cost", label: "Cost" },
  { href: "/redteam", label: "Red Team" },
  { href: "/policies", label: "Policies" },
];

export function TopNav() {
  const pathname = usePathname();
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const res = await healthcheck();
      if (!cancelled) setHealthy(res?.status === "ok");
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="container flex h-12 items-center gap-6">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span aria-hidden>🛡</span>
          <span className="tracking-tight">Sentinel</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {links.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "rounded-md px-2.5 py-1 transition-colors hover:bg-muted",
                  active
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground"
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant="allow" className="lowercase">
            dev
          </Badge>
          <Badge
            variant={
              healthy === null ? "secondary" : healthy ? "allow" : "deny"
            }
            title="Sentinel /healthz"
          >
            <span
              className={cn(
                "mr-1 inline-block h-1.5 w-1.5 rounded-full",
                healthy === null
                  ? "bg-zinc-400"
                  : healthy
                    ? "bg-emerald-400"
                    : "bg-red-400"
              )}
            />
            gemini{" "}
            {healthy === null ? "..." : healthy ? "online" : "offline"}
          </Badge>
        </div>
      </div>
    </header>
  );
}
