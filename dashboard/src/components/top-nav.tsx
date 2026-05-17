"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { healthcheck } from "@/lib/sentinelApi";
import { SentinelMark } from "@/components/logo";

const links = [
  { href: "/", label: "Activity" },
  { href: "/receipts", label: "Receipts" },
  { href: "/cost", label: "Spend" },
  { href: "/redteam", label: "Red team" },
  { href: "/policies", label: "Policies" },
];

interface Health {
  status?: string;
  gemini_configured?: boolean;
  flash_model?: string;
  pro_model?: string;
}

export function TopNav() {
  const pathname = usePathname();
  const [health, setHealth] = useState<Health | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await healthcheck();
        if (cancelled) return;
        setHealth(res);
        setReachable(res?.status === "ok");
      } catch {
        if (cancelled) return;
        setReachable(false);
      }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const geminiOn = !!health?.gemini_configured;

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-12 w-full max-w-[1400px] items-center gap-6 px-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-foreground transition-colors hover:text-primary"
        >
          <SentinelMark size={18} className="text-primary" />
          <span className="text-[13px] font-semibold tracking-tight">
            sentinel
          </span>
          <span className="ml-1 hidden text-[10px] uppercase tracking-[0.12em] text-muted-foreground md:inline">
            governance plane
          </span>
        </Link>
        <nav className="flex items-center gap-0.5 text-[13px]">
          {links.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "rounded-sm px-2.5 py-1 transition-colors",
                  active
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {l.label}
                {active && (
                  <div className="mt-1 h-[2px] w-full rounded-full bg-primary" />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3 text-[11px] text-muted-foreground">
          <StatusDot
            label="postgres"
            on={reachable === true}
            offTip="gateway unreachable"
          />
          <StatusDot
            label={geminiOn ? "gemini live" : "gemini stub"}
            on={geminiOn}
            onTip={`${health?.flash_model ?? "flash"} / ${health?.pro_model ?? "pro"}`}
            offTip="GEMINI_API_KEY not set — stub gates active"
          />
          <span className="hidden mono text-[10px] text-muted-foreground/80 md:inline">
            v0.1.0
          </span>
        </div>
      </div>
    </header>
  );
}

function StatusDot({
  label,
  on,
  onTip,
  offTip,
}: {
  label: string;
  on: boolean;
  onTip?: string;
  offTip?: string;
}) {
  return (
    <span
      title={on ? onTip ?? label : offTip ?? label}
      className="inline-flex items-center gap-1.5"
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          on ? "bg-emerald-400" : "bg-zinc-600"
        )}
      />
      <span className={on ? "text-foreground/80" : ""}>{label}</span>
    </span>
  );
}
