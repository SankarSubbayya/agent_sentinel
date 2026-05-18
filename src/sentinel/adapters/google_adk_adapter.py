"""Google Agent Development Kit (ADK) adapter — flagship integration.

This is Sentinel's first-class adapter. ADK is Google's first-party
framework for building Gemini-powered agents; Sentinel is built on the
same Gemini 2.5 Flash + Pro stack. Wrapping an ADK agent with Sentinel
takes three lines and gives you:

  - Pre-execution gating of every tool call (static → drift → Flash → Pro)
  - Hash-chained, HMAC-signed audit receipt per call
  - Per-business-unit cost event per call
  - Slack/Teams webhook alerts on policy violations
  - Merkle-root anchoring of the receipt log (optional)

Three integration patterns
==========================

A) Tool-level — wrap one ADK FunctionTool::

    from google.adk.tools import FunctionTool
    from sentinel.adapters import sentinelize_adk_tool

    def web_search(query: str) -> str:
        ...

    gated = sentinelize_adk_tool(
        FunctionTool(func=web_search),
        agent_id="agent-sales-01",
        tool_name="web.search",
    )

B) Agent-level — wrap a whole ADK Agent (gates every tool it uses)::

    from google.adk.agents import Agent
    from sentinel.adapters import SentinelADKAgent

    sales_agent = Agent(model="gemini-2.5-flash", tools=[web_search, fetch_url])
    governed = SentinelADKAgent(sales_agent, agent_id="agent-sales-01")

C) Runner-level — gate every tool call in an entire ADK Runner session
   (useful for multi-agent compositions)::

    from google.adk.runners import Runner
    runner = SentinelADKRunner(Runner(...), agent_id="agent-sales-01")

The adapter never touches ADK's internals or its event loop — it
intercepts via the standard `tool.run` / `tool.run_async` interface
that ADK exposes for FunctionTool and BaseTool. The Sentinel gate is
strictly *before* the tool executes; a deny converts to an error
message the LLM sees as a tool result, so the agent can choose a
compliant alternative on the next turn.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Iterable

from sentinel.adapters.core import GateOutcome, gate_tool_call


# ---- Tool-level wrap ---------------------------------------------------


def sentinelize_adk_tool(
    tool: Any,
    agent_id: str,
    tool_name: str | None = None,
    session_id: str | None = None,
) -> Any:
    """Wrap an ADK FunctionTool (or duck-typed equivalent) so its
    `run`/`run_async` is gated through Sentinel first.

    ADK tool objects expose either `run(args)` (sync) or `run_async(args)`
    (async). We patch both if present. The original method is preserved as
    `_sentinel_original_run` / `_sentinel_original_run_async` for users
    who want to bypass for debugging.

    If `tool_name` is omitted, falls back to `tool.name` or the wrapped
    function's `__name__`."""
    name = tool_name or getattr(tool, "name", None) or getattr(
        getattr(tool, "func", None), "__name__", None
    )
    if not name:
        raise TypeError(f"Object {tool!r} has no derivable tool name; pass tool_name=.")

    original_run = getattr(tool, "run", None)
    original_run_async = getattr(tool, "run_async", None)
    if original_run is None and original_run_async is None:
        raise TypeError(f"Object {tool!r} has no .run/.run_async; not an ADK tool.")

    async def _gate(args: dict[str, Any]) -> tuple[bool, str, dict[str, Any], GateOutcome]:
        outcome = await gate_tool_call(agent_id, name, args, session_id)
        if outcome.decision == "deny":
            return False, (
                f"BLOCKED by Sentinel: {outcome.rationale} "
                f"(receipt {outcome.receipt_id})"
            ), {}, outcome
        return True, "", outcome.rewritten_args or args, outcome

    if original_run_async is not None:
        async def new_run_async(args: dict[str, Any] | None = None, **kwargs: Any) -> Any:
            call_args = dict(args or {})
            call_args.update(kwargs)
            allowed, blocked_msg, gated_args, _ = await _gate(call_args)
            if not allowed:
                return blocked_msg
            return await original_run_async(gated_args)

        tool._sentinel_original_run_async = original_run_async  # type: ignore[attr-defined]
        tool.run_async = new_run_async  # type: ignore[attr-defined]

    if original_run is not None:
        def new_run(args: dict[str, Any] | None = None, **kwargs: Any) -> Any:
            call_args = dict(args or {})
            call_args.update(kwargs)
            try:
                loop = asyncio.get_running_loop()
                allowed, blocked_msg, gated_args, _ = loop.run_until_complete(_gate(call_args))
            except RuntimeError:
                allowed, blocked_msg, gated_args, _ = asyncio.run(_gate(call_args))
            if not allowed:
                return blocked_msg
            return original_run(gated_args)

        tool._sentinel_original_run = original_run  # type: ignore[attr-defined]
        tool.run = new_run  # type: ignore[attr-defined]

    tool._sentinel_agent_id = agent_id  # type: ignore[attr-defined]
    tool._sentinel_tool_name = name  # type: ignore[attr-defined]
    return tool


# ---- Agent-level wrap --------------------------------------------------


@dataclass
class SentinelADKAgent:
    """Wraps an ADK Agent so every tool the agent invokes is gated.

    On construction, the wrapper iterates `agent.tools` (or the
    common variants `agent._tools`, `agent.tool_set`) and replaces
    each with a sentinelized version. The agent object itself is
    returned via `.agent` and is fully drop-in usable everywhere the
    original was.

    The Sentinel agent_id is supplied per Sentinel-Agent wrapping;
    do NOT confuse with ADK's internal agent name. Sentinel agent_id
    identifies the *business principal* (e.g. agent-sales-01); ADK
    agent identity is independent."""

    agent: Any
    agent_id: str
    session_id: str | None = None
    tool_name_map: dict[str, str] | None = None  # ADK tool name -> Sentinel tool name

    def __post_init__(self) -> None:
        self._wrap_tools()

    def _candidate_tool_lists(self) -> Iterable[tuple[Any, list[Any]]]:
        """Yield (owner, list) pairs for every place we know ADK keeps tools.
        We patch each list in-place."""
        for attr in ("tools", "_tools", "tool_set", "_tool_set"):
            owner = self.agent
            tools = getattr(owner, attr, None)
            if isinstance(tools, list):
                yield owner, tools

    def _sentinel_name_for(self, tool: Any, default: str) -> str:
        if self.tool_name_map:
            adk_name = getattr(tool, "name", None) or default
            return self.tool_name_map.get(adk_name, adk_name)
        return default

    def _wrap_tools(self) -> None:
        wrapped_any = False
        for _owner, tools in self._candidate_tool_lists():
            for i, t in enumerate(list(tools)):
                adk_name = getattr(t, "name", None) or getattr(
                    getattr(t, "func", None), "__name__", f"tool_{i}"
                )
                sentinel_name = self._sentinel_name_for(t, adk_name)
                wrapped = sentinelize_adk_tool(
                    t,
                    agent_id=self.agent_id,
                    tool_name=sentinel_name,
                    session_id=self.session_id,
                )
                tools[i] = wrapped
                wrapped_any = True
        if not wrapped_any:
            # Not fatal — the agent may register tools at run time. Caller
            # can call `.refresh()` after a tool is added.
            pass

    def refresh(self) -> None:
        """Re-scan `agent.tools` and wrap any newly added entries."""
        self._wrap_tools()


# ---- Runner-level helper ----------------------------------------------


def gate_runner_session(runner: Any, agent_id: str, session_id: str | None = None) -> Any:
    """Walk every agent in an ADK Runner (multi-agent compositions) and
    wrap each agent's tools. Returns the runner unchanged."""
    agents = getattr(runner, "agents", None) or getattr(runner, "_agents", None) or []
    if not isinstance(agents, (list, tuple)):
        agents = [agents]
    for sub_agent in agents:
        SentinelADKAgent(agent=sub_agent, agent_id=agent_id, session_id=session_id)
    return runner
