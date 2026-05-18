"""Native framework adapters — drop Sentinel in front of any agent
framework without touching the framework's code.

Every adapter ultimately calls the same `gate_and_record(call, agent)`
function from `sentinel.gateway.pipeline`, so audit + cost coverage is
identical regardless of which framework the agent is running on.

**Flagship: Google Agent Development Kit (ADK)** — Sentinel's gating
pipeline is built on Gemini 2.5 Flash + Pro with Cached Content, the
same Gemini stack ADK targets. The ADK adapter wraps a `FunctionTool`,
an entire `Agent`, or the ADK `Runner` itself; every model decision
and every tool call flows through the Sentinel governance plane.

Other adapters (provided for portability):
  - anthropic_adapter   — Anthropic Agent SDK (Claude tool-use)
  - openai_adapter      — OpenAI tool-calling response shape
  - crewai_adapter      — CrewAI BaseTool subclass
  - mcp_adapter         — generic MCP `tools/call` envelope (canonical case)
"""
from sentinel.adapters.a2a_adapter import SentinelA2AClient
from sentinel.adapters.core import SentinelGate, gate_tool_call, sentinel_gated
from sentinel.adapters.google_adk_adapter import (
    SentinelADKAgent,
    sentinelize_adk_tool,
)
from sentinel.adapters.mcp_adapter import MCPSentinelAdapter

__all__ = [
    "SentinelGate",
    "gate_tool_call",
    "sentinel_gated",
    "SentinelADKAgent",
    "sentinelize_adk_tool",
    "SentinelA2AClient",
    "MCPSentinelAdapter",
]
