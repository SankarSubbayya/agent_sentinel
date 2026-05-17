"""Wire-level Pydantic models shared by the gateway and gating modules."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Inbound (MCP-shaped) ----


class ToolCallRequest(BaseModel):
    """An MCP-style `tools/call` envelope as Sentinel receives it."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    session_id: str
    # When a header-derived JWT identifies the agent, the gateway populates these.
    # In dev we accept them in the body.
    agent_id: str | None = None


class GateDecision(BaseModel):
    """The structured output schema we ask Flash for."""

    decision: Literal["allow", "deny", "rewrite"]
    confidence: float = Field(ge=0.0, le=1.0)
    escalate: bool
    rationale: str
    redactions: list[str] = Field(default_factory=list)
    rewritten_args: dict[str, Any] | None = None


# ---- Outbound ----


class ToolCallResponse(BaseModel):
    decision: Literal["allow", "deny", "rewrite"]
    receipt_id: UUID
    rationale: str
    rewritten_args: dict[str, Any] | None = None
    cost_usd: float
    latency_ms: int


# ---- Internal records ----


class AgentRecord(BaseModel):
    agent_id: str
    name: str
    bu: str
    role: str
    declared_goal: str | None = None


class AuditReceiptRecord(BaseModel):
    receipt_id: UUID
    agent_id: str
    session_id: str
    tool: str
    args_hash: str
    decision: Literal["allow", "deny", "rewrite"]
    decided_by: Literal["static", "flash", "pro"]
    confidence: float | None
    escalated: bool
    rationale: str
    rationale_hash: str
    policy_versions_used: list[dict[str, str]]
    gemini_cache_ids: list[str]
    gemini_trace_id: str | None
    prev_hash: str | None
    self_hash: str
    signature: str
    latency_ms: int
    created_at: datetime
