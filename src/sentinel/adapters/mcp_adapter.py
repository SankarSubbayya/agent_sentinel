"""Generic MCP adapter — the canonical envelope shape Sentinel already speaks.

For agents using `fastmcp` or any MCP client, the request shape is already
`tools/call { name, arguments }`. This adapter exposes a helper that takes
an MCP request, gates it via Sentinel, and returns an MCP-shaped response.

The HTTP gateway `/v1/tools/call` is also MCP-compatible — this in-process
adapter is for agents that import Sentinel directly."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sentinel.adapters.core import GateOutcome, gate_tool_call


@dataclass(slots=True)
class MCPSentinelAdapter:
    """In-process gate for an MCP-shaped tool call.

    Methods accept either the standard MCP envelope
        {"name": "<tool>", "arguments": {...}}
    or a more permissive `tool`+`args` form."""

    agent_id: str
    session_id: str | None = None

    @staticmethod
    def _normalize(envelope: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        name = envelope.get("name") or envelope.get("tool")
        if not name:
            raise ValueError("MCP envelope must include 'name' (or 'tool').")
        args = envelope.get("arguments") if "arguments" in envelope else envelope.get("args", {})
        return name, dict(args or {})

    async def gate(self, envelope: dict[str, Any]) -> GateOutcome:
        name, args = self._normalize(envelope)
        return await gate_tool_call(self.agent_id, name, args, self.session_id)

    async def gate_and_format(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Returns an MCP-style response with Sentinel's decision attached."""
        outcome = await self.gate(envelope)
        return {
            "name": envelope.get("name") or envelope.get("tool"),
            "sentinel": {
                "decision": outcome.decision,
                "receipt_id": outcome.receipt_id,
                "rationale": outcome.rationale,
                "cost_usd": outcome.cost_usd,
                "latency_ms": outcome.latency_ms,
            },
            "arguments": outcome.rewritten_args or envelope.get("arguments"),
        }
