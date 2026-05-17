import { cn } from "@/lib/utils";
import type { Decision } from "@/lib/sentinelApi";

const styles: Record<Decision, string> = {
  allow:
    "text-emerald-300 border-emerald-500/40 bg-emerald-500/10",
  deny: "text-red-300 border-red-500/40 bg-red-500/10",
  rewrite: "text-amber-300 border-amber-500/40 bg-amber-500/10",
};

const glyphs: Record<Decision, string> = {
  allow: "●",
  deny: "✕",
  rewrite: "↻",
};

export function DecisionBadge({
  decision,
  className,
}: {
  decision: Decision;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        styles[decision],
        className
      )}
    >
      <span className="text-[8px] leading-none">{glyphs[decision]}</span>
      {decision}
    </span>
  );
}

export function TierPill({ tier }: { tier: "static" | "flash" | "pro" }) {
  const klass = `tier-pill tier-${tier}`;
  return <span className={klass}>{tier}</span>;
}
