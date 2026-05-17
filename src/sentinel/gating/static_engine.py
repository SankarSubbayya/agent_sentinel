"""Fast pre-LLM filter: regex denylists, ACLs, hard rules.

Must return in <5ms. If it doesn't fire, the call flows to Flash."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from sentinel.models import AgentRecord, ToolCallRequest


@dataclass(slots=True)
class StaticVerdict:
    decision: Literal["allow", "deny", "pass"]  # "pass" = no static rule fired
    rationale: str
    rule_id: str | None = None


# Plaintext PII patterns we never want shipped to external tools.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

# Tools that are role-gated. The Flash gate adjudicates intent within these.
_ROLE_TOOL_ACL: dict[str, set[str]] = {
    "researcher": {"web.search", "web.fetch", "crm.read", "email.send_internal"},
    "analyst": {
        "db.read", "ledger.read", "report.write",
        "email.send_internal", "email.send_external",
    },
    "ops": {
        "crm.read", "crm.update", "refund.issue",
        "email.send_internal", "email.send_external",
    },
}

# Tools we hard-deny regardless of role until policy explicitly opens them.
_GLOBAL_DENY: set[str] = {"shell.exec", "fs.write_anywhere", "dns.update"}

# Refund issuance dollar cap — anything beyond is a deny at the static layer.
_REFUND_HARD_CAP_USD = 500.0


def _flatten_args(args: dict[str, Any]) -> str:
    """Best-effort string view of args for regex matching."""
    return " ".join(f"{k}={v!s}" for k, v in args.items())


def evaluate_static(call: ToolCallRequest, agent: AgentRecord) -> StaticVerdict:
    # Hard global deny.
    if call.tool in _GLOBAL_DENY:
        return StaticVerdict("deny", f"Tool '{call.tool}' is on the global denylist.", "global_deny")

    # Role-based ACL: if a role has an explicit allowlist, the tool must be in it.
    allowed = _ROLE_TOOL_ACL.get(agent.role)
    if allowed is not None and call.tool not in allowed:
        return StaticVerdict(
            "deny",
            f"Role '{agent.role}' is not permitted to invoke tool '{call.tool}'.",
            "role_acl",
        )

    # Refund cap.
    if call.tool == "refund.issue":
        amount = float(call.args.get("amount_usd", 0) or 0)
        if amount > _REFUND_HARD_CAP_USD:
            return StaticVerdict(
                "deny",
                f"Refund amount ${amount:.2f} exceeds hard cap ${_REFUND_HARD_CAP_USD:.2f}.",
                "refund_cap",
            )

    # External-recipient PII guard. If the tool sends external messages and
    # the args contain plaintext SSN/CC, deny here. Email addresses are not
    # auto-PII — the Flash gate decides if the email body crosses a line.
    if call.tool in {"email.send_external", "webhook.post", "http.post"}:
        flat = _flatten_args(call.args)
        if _SSN_RE.search(flat):
            return StaticVerdict("deny", "Plaintext SSN detected in outbound payload.", "pii_ssn")
        if _CC_RE.search(flat):
            return StaticVerdict("deny", "Plaintext credit-card number detected in outbound payload.", "pii_cc")

    # No static rule fired — let the Flash gate reason.
    return StaticVerdict("pass", "No static rule applied; deferring to LLM gate.")
