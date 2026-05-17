import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const delta = (Date.now() - t) / 1000;
  if (delta < 1) return "just now";
  if (delta < 60) return `${Math.floor(delta)}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}

export function clockTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

const BU_COLORS: Record<string, string> = {
  sales: "bg-sky-500/15 text-sky-300 border-sky-500/40",
  finance: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40",
  ops: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  customer: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  default: "bg-zinc-500/15 text-zinc-300 border-zinc-500/40",
};

export function buColor(agentOrBu: string): string {
  const key = agentOrBu?.toLowerCase() ?? "";
  for (const k of Object.keys(BU_COLORS)) {
    if (key.includes(k)) return BU_COLORS[k];
  }
  return BU_COLORS.default;
}

// Compact agent ID — "agent-finance-01" -> "finance-01"
export function compactAgent(id: string): string {
  return id.replace(/^agent-/, "");
}

// Formats numbers like Linear: 12,345 with smart precision for tiny dollar amounts.
export function fmtUsd(usd: number): string {
  if (usd === 0) return "$0";
  if (usd < 0.01) return `$${usd.toFixed(5)}`;
  if (usd < 1) return `$${usd.toFixed(4)}`;
  return `$${usd.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
