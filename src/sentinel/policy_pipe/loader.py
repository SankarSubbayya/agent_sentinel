"""Map a (role, tool) call into the cache_ids the Pro reasoner should consult.

Pure DB lookup; no LLM. Returns a list because Pro can consume multiple caches
in one call (one per policy document)."""
from __future__ import annotations

from sentinel.policy_pipe.catalog import fetch_by_tags


# Heuristic: which domain tags are relevant to which tool families.
# Pro will still receive the call envelope and decide which sections apply.
_TOOL_TAG_HINTS: dict[str, list[str]] = {
    "email.send_external": ["PII", "vendor", "export"],
    "webhook.post":        ["PII", "vendor", "export", "security"],
    "http.post":           ["PII", "vendor", "export", "security"],
    "refund.issue":        ["financial"],
    "ledger.write":        ["financial", "retention"],
    "crm.update":          ["PII", "retention"],
    "db.read":             ["PII", "retention"],
    "report.write":        ["PII", "retention"],
    "marketing.send":      ["PII", "marketing"],
}


async def load_caches_for(tool: str, role: str) -> list[dict]:
    """Return [{id, name, version, cache_id, domain_tags}, ...] for the call."""
    tags = _TOOL_TAG_HINTS.get(tool, [])
    if not tags:
        # Unknown tool family — load everything; Pro is smart enough to pick.
        return await fetch_by_tags([])
    return await fetch_by_tags(tags)
