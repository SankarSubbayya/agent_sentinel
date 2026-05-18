"""Core SentinelGate — the single piece every framework adapter calls.

Each framework adapter normalizes its tool-call shape into a
`ToolCallRequest`, routes it through Sentinel, and converts the
gating decision back into the framework's expected response shape.
The actual gating, audit, and cost logic is shared via
`sentinel.gateway.pipeline.gate_and_record`."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import uuid4

from sentinel.models import ToolCallRequest, ToolCallResponse


@dataclass(slots=True)
class GateOutcome:
    decision: str
    receipt_id: str
    rationale: str
    rewritten_args: dict[str, Any] | None
    cost_usd: float
    latency_ms: int

    @property
    def allowed(self) -> bool:
        return self.decision in ("allow", "rewrite")

    @property
    def args(self) -> dict[str, Any]:
        """Return the effective args — rewritten if present, else (caller passes original)."""
        return self.rewritten_args  # type: ignore[return-value]


async def gate_tool_call(
    agent_id: str,
    tool: str,
    args: dict[str, Any],
    session_id: str | None = None,
) -> GateOutcome:
    """In-process gate. Adapters running in the same Python process as the
    gateway can call this directly; adapters in other processes should
    POST to /v1/tools/call instead."""
    # Lazy import to avoid the same circular gateway → adapter → pipeline
    # we already saw with the agent runner.
    from sentinel.gateway.pipeline import gate_and_record, load_agent

    agent = await load_agent(agent_id)
    call = ToolCallRequest(
        agent_id=agent_id,
        session_id=session_id or f"adapter-{uuid4().hex[:8]}",
        tool=tool,
        args=args,
    )
    result = await gate_and_record(call, agent)
    r: ToolCallResponse = result.response
    return GateOutcome(
        decision=r.decision,
        receipt_id=str(r.receipt_id),
        rationale=r.rationale,
        rewritten_args=r.rewritten_args,
        cost_usd=r.cost_usd,
        latency_ms=r.latency_ms,
    )


class SentinelGate:
    """Generic per-agent gate handle.

    Each framework adapter exposes a `SentinelGate(agent_id, session_id)`
    that callers can use to gate one tool invocation at a time:

        gate = SentinelGate("agent-sales-01")
        outcome = await gate.check("web.search", {"q": "pricing"})
        if outcome.allowed:
            result = real_web_search(**(outcome.rewritten_args or {"q": "pricing"}))
    """

    __slots__ = ("agent_id", "session_id")

    def __init__(self, agent_id: str, session_id: str | None = None) -> None:
        self.agent_id = agent_id
        self.session_id = session_id or f"sess-{uuid4().hex[:8]}"

    async def check(self, tool: str, args: dict[str, Any]) -> GateOutcome:
        return await gate_tool_call(self.agent_id, tool, args, self.session_id)

    def check_sync(self, tool: str, args: dict[str, Any]) -> GateOutcome:
        """Synchronous wrapper for frameworks that don't run on asyncio
        (CrewAI, some LangGraph tool functions). Creates an event loop if
        not already in one."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.check(tool, args))
        # If we're already in a running loop, schedule and wait.
        return loop.run_until_complete(self.check(tool, args))


# Convenience decorator — wraps a function-shaped tool so every call is
# routed through Sentinel before the real implementation runs.
def sentinel_gated(
    agent_id: str,
    tool_name: str,
    *,
    session_id: str | None = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator. Usage:

        @sentinel_gated("agent-sales-01", "web.search")
        async def web_search(q: str) -> str:
            ...

    The decorator calls Sentinel first; on `deny` raises `PermissionError`,
    on `rewrite` passes the rewritten args through to the wrapped function."""

    def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def wrapper(**kwargs: Any) -> Any:
            outcome = await gate_tool_call(agent_id, tool_name, kwargs, session_id)
            if outcome.decision == "deny":
                raise PermissionError(
                    f"Sentinel denied {tool_name}: {outcome.rationale} "
                    f"(receipt {outcome.receipt_id})"
                )
            effective_kwargs = outcome.rewritten_args or kwargs
            return await fn(**effective_kwargs)

        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return deco
