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

const BU_COLORS: Record<string, string> = {
  sales: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  finance: "bg-purple-500/20 text-purple-300 border-purple-500/40",
  ops: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  customer: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  default: "bg-zinc-500/20 text-zinc-300 border-zinc-500/40",
};

export function buColor(agentOrBu: string): string {
  const key = agentOrBu?.toLowerCase() ?? "";
  for (const k of Object.keys(BU_COLORS)) {
    if (key.includes(k)) return BU_COLORS[k];
  }
  return BU_COLORS.default;
}
