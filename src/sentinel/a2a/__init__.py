"""Google A2A (Agent-to-Agent) protocol support for Sentinel.

A2A is the open standard for agent-to-agent communication — counterpart to
MCP (agent-to-tool). Sentinel gates BOTH:

  - MCP `tools/call` → src/sentinel/gateway/app.py POST /v1/tools/call
  - A2A `tasks/send` → src/sentinel/a2a/server.py POST /a2a/v1/tasks/send

Sentinel exposes its own A2A agent card at /.well-known/agent.json so
other A2A peers can discover the Sentinel governance plane and route
their inter-agent traffic through it for inline policy enforcement,
audit trails, and per-BU cost attribution.

Spec reference: https://google.github.io/A2A/
"""
from sentinel.a2a.models import A2ATask, A2ATaskStatus, AgentCard
from sentinel.a2a.server import a2a_router, sentinel_agent_card

__all__ = [
    "A2ATask",
    "A2ATaskStatus",
    "AgentCard",
    "a2a_router",
    "sentinel_agent_card",
]
