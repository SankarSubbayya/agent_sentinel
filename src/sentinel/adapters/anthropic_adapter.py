"""Anthropic Agent SDK adapter — intercepts Claude tool-use calls.

Usage:

    from anthropic import Anthropic
    from sentinel.adapters.anthropic_adapter import SentinelAnthropicGate

    client = Anthropic()
    gate = SentinelAnthropicGate(agent_id="agent-sales-01")

    response = client.messages.create(model="claude-sonnet-4-6", tools=[...], ...)
    for block in response.content:
        if block.type == "tool_use":
            outcome = await gate.check_tool_use(block)
            if outcome.allowed:
                result = real_run_tool(block.name, outcome.rewritten_args or block.input)
            else:
                result = f"BLOCKED: {outcome.rationale}"

The adapter normalizes Anthropic's `tool_use` block shape into a
ToolCallRequest, gates it via `gate_and_record`, and returns a
GateOutcome the caller can act on."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sentinel.adapters.core import GateOutcome, gate_tool_call


@dataclass(slots=True)
class SentinelAnthropicGate:
    agent_id: str
    session_id: str | None = None

    async def check_tool_use(self, tool_use_block: Any) -> GateOutcome:
        """Accept a `messages.create` `tool_use` content block (object or dict).
        Extracts the tool name + input dict and routes through Sentinel."""
        if hasattr(tool_use_block, "name"):
            tool_name = tool_use_block.name
            tool_input = dict(tool_use_block.input or {})
        else:
            tool_name = tool_use_block["name"]
            tool_input = dict(tool_use_block.get("input") or {})
        return await gate_tool_call(
            agent_id=self.agent_id,
            tool=tool_name,
            args=tool_input,
            session_id=self.session_id,
        )

    def to_tool_result(self, tool_use_id: str, outcome: GateOutcome, tool_result: str) -> dict:
        """Build the Anthropic-shaped `tool_result` content block that
        gets sent back to the model on the next turn."""
        if outcome.decision == "deny":
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "is_error": True,
                "content": (
                    f"BLOCKED by Sentinel: {outcome.rationale} "
                    f"(receipt {outcome.receipt_id})"
                ),
            }
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": tool_result,
        }
