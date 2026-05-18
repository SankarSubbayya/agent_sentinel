"""OpenAI adapter — for agents using OpenAI's tool-calling response shape.

OpenAI's chat completions return tool calls as:
    {"id": "call_…", "type": "function", "function": {"name": "...", "arguments": "{...}"}}

The `arguments` field is a JSON-encoded string, not an object. This
adapter parses it, gates via Sentinel, and helps construct the followup
`role: tool` message back to the model."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sentinel.adapters.core import GateOutcome, gate_tool_call


@dataclass(slots=True)
class SentinelOpenAIGate:
    agent_id: str
    session_id: str | None = None

    async def check(self, tool_call: dict[str, Any]) -> GateOutcome:
        fn = tool_call.get("function") or {}
        name = fn.get("name") or tool_call.get("name")
        raw_args = fn.get("arguments") or tool_call.get("arguments") or "{}"
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {"raw": raw_args}
        else:
            args = dict(raw_args)
        if not name:
            raise ValueError("OpenAI tool_call missing function name.")
        return await gate_tool_call(self.agent_id, name, args, self.session_id)

    def to_tool_message(self, tool_call_id: str, outcome: GateOutcome, tool_result: str) -> dict[str, Any]:
        if outcome.decision == "deny":
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": (
                    f"BLOCKED by Sentinel: {outcome.rationale} "
                    f"(receipt {outcome.receipt_id})"
                ),
            }
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": tool_result,
        }
