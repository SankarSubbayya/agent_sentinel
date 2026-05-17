"""Lightweight intent-drift signal.

Looks for: (1) prompt-injection markers in args, (2) tool category change
relative to declared goal, (3) fresh external recipients not seen in recent
history. Cheap — runs before Flash, used to bias the escalate flag."""
from __future__ import annotations

import re
from typing import Any

from sentinel.models import AgentRecord, ToolCallRequest


_INJECTION_RE = re.compile(
    r"(ignore (all )?previous|disregard your goal|new instructions|"
    r"override the system|forward to (attacker|external|new)|wire to|exfiltrate)",
    re.IGNORECASE,
)

# Words that hint the call is an external-comms action.
_EXTERNAL_TOOLS = {"email.send_external", "webhook.post", "http.post"}


def drift_signal(
    call: ToolCallRequest,
    agent: AgentRecord,
    recent: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    """Return (escalate, reason). reason==None means no signal."""
    flat = " ".join(f"{k}={v}" for k, v in call.args.items())

    if _INJECTION_RE.search(flat):
        return True, "injection_markers_in_args"

    # Goal mismatch: declared goal doesn't mention the verb-family of the tool.
    goal = (agent.declared_goal or "").lower()
    if call.tool == "refund.issue" and "refund" not in goal:
        return True, "tool_outside_declared_goal:refund.issue"
    if call.tool in _EXTERNAL_TOOLS and "external" not in goal and "vendor" not in goal:
        # Fresh external recipient?
        recipient = str(call.args.get("to", "") or call.args.get("url", ""))
        recent_tools = {r["tool"] for r in recent[:20]}
        if call.tool not in recent_tools and recipient:
            return True, f"fresh_external_recipient:{recipient[:64]}"

    return False, None
