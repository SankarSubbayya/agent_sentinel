import { Badge } from "@/components/ui/badge";
import type { Decision } from "@/lib/sentinelApi";

export function DecisionBadge({ decision }: { decision: Decision }) {
  const variant =
    decision === "allow"
      ? "allow"
      : decision === "deny"
        ? "deny"
        : "rewrite";
  return (
    <Badge variant={variant} className="uppercase tracking-wide">
      {decision}
    </Badge>
  );
}
