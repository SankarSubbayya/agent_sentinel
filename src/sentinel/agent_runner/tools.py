"""Tool catalog + deterministic mock executors.

Each tool is declared once with: (1) a Gemini function-calling schema so the
LLM can pick it, (2) which roles are permitted to invoke it (this aligns with
the static engine's ACL), and (3) a mock executor that returns plausible
output so the agent has something to reason about on subsequent turns.

Sentinel never actually calls a CRM or sends an email — the value is in the
gating + audit + cost loop. The mock executors give the demo a believable
shape."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class ToolDecl:
    name: str
    description: str
    parameters: dict[str, Any]  # Gemini-compatible JSON schema
    allowed_roles: set[str]
    mock: Callable[[dict[str, Any]], str]


def _mock_web_search(args: dict[str, Any]) -> str:
    q = str(args.get("q", "")).lower()
    if "pricing" in q or "price" in q:
        return (
            "3 results:\n"
            "  - Acme Pro tier: $499/mo (50 seats)\n"
            "  - Acme Enterprise tier: $1,299/mo (250 seats)\n"
            "  - Competitor 'Beta' Pro: $429/mo (50 seats, 1yr)"
        )
    if "refund" in q or "policy" in q:
        return "2 results: ACME refund procedures page; ACME refund FAQ for customers."
    return "3 generic search results returned."


def _mock_web_fetch(args: dict[str, Any]) -> str:
    url = str(args.get("url", ""))
    return f"Fetched {url} (12.4 KB). Title: 'Q3 2026 Competitor Pricing Tracker'."


def _mock_crm_read(args: dict[str, Any]) -> str:
    cid = str(args.get("customer_id", "?"))
    return (
        f"Customer {cid}: account_status=active, mrr=$249, "
        f"last_ticket=#5512 (lost-in-transit), refund_to_date=$0."
    )


def _mock_crm_update(args: dict[str, Any]) -> str:
    cid = str(args.get("customer_id", "?"))
    return f"Updated CRM record for {cid}."


def _mock_refund_issue(args: dict[str, Any]) -> str:
    cid = str(args.get("customer_id", "?"))
    amt = args.get("amount_usd", 0)
    return f"Refund queued: customer={cid} amount=${amt}. Will settle in 2-3 business days."


def _mock_db_read(args: dict[str, Any]) -> str:
    q = str(args.get("query", ""))
    return f"db.read returned 4 rows. (mock query: {q[:80]}...)"


def _mock_ledger_read(args: dict[str, Any]) -> str:
    return "ledger.read: Q2 reconciliation balance = $1,284,029.17 across 12 accounts."


def _mock_report_write(args: dict[str, Any]) -> str:
    title = str(args.get("title", "untitled"))
    return f"Report '{title}' saved to /reports/auto. 1 page, 432 words."


def _mock_email_internal(args: dict[str, Any]) -> str:
    to = str(args.get("to", "?"))
    return f"Internal email sent to {to}."


def _mock_email_external(args: dict[str, Any]) -> str:
    to = str(args.get("to", "?"))
    return f"External email sent to {to}."


CATALOG: dict[str, ToolDecl] = {
    "web.search": ToolDecl(
        name="web.search",
        description="Run a web search and return up to 3 result snippets.",
        parameters={
            "type": "object",
            "properties": {"q": {"type": "string", "description": "Search query."}},
            "required": ["q"],
        },
        allowed_roles={"researcher"},
        mock=_mock_web_search,
    ),
    "web.fetch": ToolDecl(
        name="web.fetch",
        description="Fetch the text content of a public web URL.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        allowed_roles={"researcher"},
        mock=_mock_web_fetch,
    ),
    "crm.read": ToolDecl(
        name="crm.read",
        description="Look up a customer record by ID.",
        parameters={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
        allowed_roles={"researcher", "ops"},
        mock=_mock_crm_read,
    ),
    "crm.update": ToolDecl(
        name="crm.update",
        description="Update a field on a customer record.",
        parameters={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "field": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["customer_id", "field", "value"],
        },
        allowed_roles={"ops"},
        mock=_mock_crm_update,
    ),
    "refund.issue": ToolDecl(
        name="refund.issue",
        description="Issue a refund to a customer for a given USD amount with a free-text memo. Use whatever amount the brief specifies.",
        parameters={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount_usd": {"type": "number"},
                "memo": {"type": "string"},
            },
            "required": ["customer_id", "amount_usd", "memo"],
        },
        allowed_roles={"ops"},
        mock=_mock_refund_issue,
    ),
    "db.read": ToolDecl(
        name="db.read",
        description="Run a parameterized SQL query against the analytics warehouse.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        allowed_roles={"analyst"},
        mock=_mock_db_read,
    ),
    "ledger.read": ToolDecl(
        name="ledger.read",
        description="Read financial ledger entries.",
        parameters={
            "type": "object",
            "properties": {"period": {"type": "string"}},
            "required": ["period"],
        },
        allowed_roles={"analyst"},
        mock=_mock_ledger_read,
    ),
    "report.write": ToolDecl(
        name="report.write",
        description="Save a report.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["title", "body"],
        },
        allowed_roles={"analyst"},
        mock=_mock_report_write,
    ),
    "email.send_internal": ToolDecl(
        name="email.send_internal",
        description="Send an email to an internal address (acme.internal or acme-corp.com).",
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
        allowed_roles={"researcher", "analyst", "ops"},
        mock=_mock_email_internal,
    ),
    "email.send_external": ToolDecl(
        name="email.send_external",
        description="Send an email to an external recipient with subject and body.",
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
        allowed_roles={"analyst", "ops"},
        mock=_mock_email_external,
    ),
}


def tools_for_role(role: str) -> list[ToolDecl]:
    return [t for t in CATALOG.values() if role in t.allowed_roles]


def mock_execute(tool_name: str, args: dict[str, Any]) -> str:
    decl = CATALOG.get(tool_name)
    if decl is None:
        return f"Tool '{tool_name}' is not in the catalog."
    return decl.mock(args)
