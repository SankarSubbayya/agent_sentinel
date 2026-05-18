"""A2A protocol envelope models (minimal subset).

We implement the subset Sentinel needs to (a) advertise itself as a
governance peer and (b) gate task-send requests. The full A2A surface
(tasks/get, tasks/cancel, push notifications, sendSubscribe streaming)
can be added incrementally — for v1 a synchronous tasks/send is enough
to demonstrate inter-agent gating."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---- Agent Card -----------------------------------------------------------


class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    inputModes: list[str] = Field(default_factory=lambda: ["text"])
    outputModes: list[str] = Field(default_factory=lambda: ["text"])


class AgentCardCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = True


class AgentCardAuth(BaseModel):
    schemes: list[str] = Field(default_factory=lambda: ["bearer"])


class AgentCard(BaseModel):
    """https://google.github.io/A2A/specification/agent-card/"""

    name: str
    description: str
    url: str
    version: str
    provider: dict[str, str] | None = None
    capabilities: AgentCardCapabilities = Field(default_factory=AgentCardCapabilities)
    authentication: AgentCardAuth = Field(default_factory=AgentCardAuth)
    defaultInputModes: list[str] = Field(default_factory=lambda: ["text", "data"])
    defaultOutputModes: list[str] = Field(default_factory=lambda: ["text", "data"])
    skills: list[AgentSkill] = Field(default_factory=list)


# ---- Tasks ---------------------------------------------------------------


TaskState = Literal[
    "submitted",
    "working",
    "input-required",
    "completed",
    "canceled",
    "failed",
]


class A2ATaskStatus(BaseModel):
    state: TaskState
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message: dict[str, Any] | None = None


class A2APart(BaseModel):
    type: Literal["text", "file", "data"]
    text: str | None = None
    file: dict[str, Any] | None = None
    data: dict[str, Any] | None = None


class A2AMessage(BaseModel):
    role: Literal["user", "agent"] = "user"
    parts: list[A2APart] = Field(default_factory=list)


class A2ATask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    sessionId: str | None = None
    status: A2ATaskStatus
    history: list[A2AMessage] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- tasks/send request envelope -----------------------------------------


class TaskSendParams(BaseModel):
    """A2A `tasks/send` parameters. The envelope is JSON-RPC-like
    (method/params) but for simplicity we accept it directly as the
    POST body."""

    id: str | None = None
    sessionId: str | None = None
    message: A2AMessage
    metadata: dict[str, Any] = Field(default_factory=dict)


class SentinelTaskSendParams(TaskSendParams):
    """Extends A2A `tasks/send` with the Sentinel routing fields we need
    to identify the *originating business agent* (whose actions get
    governed) and the *target peer* (where the task is being delegated)."""

    sentinel_agent_id: str = Field(
        ...,
        description="Sentinel-registered agent_id whose actions are being governed (the principal).",
    )
    target_agent: str = Field(
        ...,
        description="Logical name of the destination A2A peer (e.g. 'summary-agent', 'translator-agent').",
    )
    intent: str | None = Field(
        None,
        description="Optional short verb/intent (default: derived from message text). Used as the gated 'tool' name in the audit receipt as 'agent.delegate.<target>'.",
    )
