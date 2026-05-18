"""Unit tests for the static policy engine — pure-Python, no DB."""
from __future__ import annotations

import pytest

from sentinel.gating.static_engine import evaluate_static
from sentinel.models import AgentRecord, ToolCallRequest


SALES = AgentRecord(agent_id="agent-sales-01", name="Sales", bu="Sales", role="researcher",
                    declared_goal="Find competitor pricing.")
OPS = AgentRecord(agent_id="agent-ops-01", name="Ops", bu="CustomerOps", role="ops",
                  declared_goal="Process customer refund requests.")
FINANCE = AgentRecord(agent_id="agent-finance-01", name="Finance", bu="Finance", role="analyst",
                      declared_goal="Prepare monthly close package.")


def _call(agent_role: str, tool: str, args: dict) -> tuple[ToolCallRequest, AgentRecord]:
    agent = {"researcher": SALES, "ops": OPS, "analyst": FINANCE}[agent_role]
    return (
        ToolCallRequest(agent_id=agent.agent_id, session_id="t", tool=tool, args=args),
        agent,
    )


class TestGlobalDeny:
    def test_shell_exec_denied(self) -> None:
        call, agent = _call("ops", "shell.exec", {"cmd": "ls"})
        v = evaluate_static(call, agent)
        assert v.decision == "deny"
        assert v.rule_id == "global_deny"

    def test_dns_update_denied(self) -> None:
        call, agent = _call("ops", "dns.update", {"x": 1})
        assert evaluate_static(call, agent).decision == "deny"

    def test_fs_write_anywhere_denied(self) -> None:
        call, agent = _call("ops", "fs.write_anywhere", {"path": "/etc"})
        assert evaluate_static(call, agent).decision == "deny"


class TestRoleACL:
    def test_sales_cannot_refund(self) -> None:
        call, agent = _call("researcher", "refund.issue", {"customer_id": "X", "amount_usd": 1})
        v = evaluate_static(call, agent)
        assert v.decision == "deny"
        assert v.rule_id == "role_acl"

    def test_analyst_cannot_refund(self) -> None:
        call, agent = _call("analyst", "refund.issue", {"customer_id": "X", "amount_usd": 1})
        assert evaluate_static(call, agent).decision == "deny"

    def test_ops_can_refund(self) -> None:
        call, agent = _call("ops", "refund.issue", {"customer_id": "X", "amount_usd": 1, "memo": "t"})
        # Pass means "defer to LLM gate" — static didn't fire.
        assert evaluate_static(call, agent).decision == "pass"

    def test_unknown_tool_denied_for_acl_role(self) -> None:
        call, agent = _call("researcher", "made.up.tool", {})
        assert evaluate_static(call, agent).decision == "deny"


class TestRefundCap:
    def test_under_cap_passes(self) -> None:
        call, agent = _call("ops", "refund.issue", {"customer_id": "X", "amount_usd": 100, "memo": "t"})
        assert evaluate_static(call, agent).decision == "pass"

    def test_at_cap_passes(self) -> None:
        call, agent = _call("ops", "refund.issue", {"customer_id": "X", "amount_usd": 500, "memo": "t"})
        # Cap is exclusive-upper: 500 exactly is allowed.
        assert evaluate_static(call, agent).decision == "pass"

    def test_one_cent_over_cap_denied(self) -> None:
        call, agent = _call("ops", "refund.issue", {"customer_id": "X", "amount_usd": 500.01, "memo": "t"})
        v = evaluate_static(call, agent)
        assert v.decision == "deny"
        assert v.rule_id == "refund_cap"

    def test_huge_amount_denied(self) -> None:
        call, agent = _call("ops", "refund.issue", {"customer_id": "X", "amount_usd": 9999999, "memo": "t"})
        assert evaluate_static(call, agent).decision == "deny"


class TestPIIRegex:
    def test_ssn_denied_outbound_email(self) -> None:
        """Ops agent has email.send_external in its ACL — so the call
        reaches the PII check, which fires on the SSN regex."""
        call, agent = _call("ops", "email.send_external",
                            {"to": "x@y", "body": "ssn 123-45-6789"})
        v = evaluate_static(call, agent)
        assert v.decision == "deny"
        assert v.rule_id == "pii_ssn"

    @pytest.mark.parametrize("tool", ["webhook.post", "http.post"])
    def test_unpermitted_outbound_denied_at_role(self, tool: str) -> None:
        """webhook.post / http.post aren't in any demo role's allowlist —
        defense-in-depth: role ACL fires before PII regex. This is correct;
        the tool would never reach Flash regardless of payload."""
        call, agent = _call("ops", tool, {"url": "x", "body": "ssn 123-45-6789"})
        v = evaluate_static(call, agent)
        assert v.decision == "deny"
        assert v.rule_id == "role_acl"

    def test_cc_denied_outbound(self) -> None:
        call, agent = _call("ops", "email.send_external",
                            {"to": "x@y", "subject": "card", "body": "4111 1111 1111 1111"})
        v = evaluate_static(call, agent)
        assert v.decision == "deny"
        assert v.rule_id == "pii_cc"

    def test_ssn_in_internal_email_allowed(self) -> None:
        # Internal-channel PII isn't auto-denied; Flash decides instead.
        call, agent = _call("ops", "email.send_internal",
                            {"to": "x@y.internal", "body": "ssn 123-45-6789"})
        assert evaluate_static(call, agent).decision == "pass"
