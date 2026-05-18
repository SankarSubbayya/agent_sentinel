"""CrewAI adapter — wrap a CrewAI tool so every invocation gates through Sentinel.

CrewAI tools subclass `crewai.tools.BaseTool` and expose `_run`. This
adapter installs a pre-invocation gate.

Usage:

    from crewai.tools import BaseTool
    from sentinel.adapters.crewai_adapter import sentinelize_crewai_tool

    class WebSearch(BaseTool):
        name: str = "web.search"
        def _run(self, query: str) -> str:
            ...

    gated = sentinelize_crewai_tool(WebSearch(), agent_id="agent-sales-01")
"""
from __future__ import annotations

import asyncio
from typing import Any

from sentinel.adapters.core import gate_tool_call


def sentinelize_crewai_tool(
    tool: Any,
    agent_id: str,
    tool_name: str | None = None,
    session_id: str | None = None,
) -> Any:
    """Wrap a CrewAI BaseTool's `_run` so it gates through Sentinel first.
    If `tool_name` is omitted, uses `tool.name`."""
    name = tool_name or getattr(tool, "name", None)
    if not name:
        raise TypeError("CrewAI tool has no `name` attribute and no tool_name given.")
    original_run = getattr(tool, "_run", None)
    if original_run is None:
        raise TypeError(f"Object {tool!r} has no ._run; not a CrewAI BaseTool.")

    def new_run(*args: Any, **kwargs: Any) -> Any:
        # Normalize positional args into a kwargs dict using the tool's signature.
        # For simplicity, we route a single canonical 'input' kwarg if positional.
        call_args = dict(kwargs)
        if args:
            call_args.setdefault("input", args[0] if len(args) == 1 else list(args))

        outcome = asyncio.run(gate_tool_call(agent_id, name, call_args, session_id))
        if outcome.decision == "deny":
            return (
                f"BLOCKED by Sentinel: {outcome.rationale} "
                f"(receipt {outcome.receipt_id}). Try a compliant alternative."
            )
        effective = outcome.rewritten_args or call_args
        return original_run(**effective)

    tool._run = new_run  # type: ignore[attr-defined]
    return tool
