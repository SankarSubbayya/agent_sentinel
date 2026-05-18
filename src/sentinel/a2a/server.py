"""A2A server endpoints — Sentinel as a governance peer in the A2A graph.

Endpoints:
  GET  /.well-known/agent.json   — Sentinel's A2A agent card
  POST /a2a/v1/tasks/send         — gate an A2A task delegation
  GET  /a2a/v1/tasks/{id}         — fetch a Sentinel-gated task by id

When Agent A wants to delegate a task to Agent B, it can send the task
to Sentinel via /a2a/v1/tasks/send instead of directly. Sentinel:
  1. Extracts the task intent (text summary of the work being delegated)
  2. Builds a virtual tool call: tool='agent.delegate.<target>', args=task
  3. Routes it through the same gate_and_record pipeline as MCP
  4. Returns an A2A Task with state=completed|failed depending on gate
     decision; on `rewrite` returns the redacted task payload."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from sentinel.a2a.models import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
    AgentCardCapabilities,
    AgentSkill,
    SentinelTaskSendParams,
)
from sentinel.db import get_session
from sentinel.models import ToolCallRequest


a2a_router = APIRouter()


def sentinel_agent_card(base_url: str = "http://127.0.0.1:8088") -> AgentCard:
    """The Sentinel A2A agent card. Identifies Sentinel as a governance
    peer that other A2A agents can route their inter-agent traffic
    through for policy enforcement, audit trails, and cost metering."""
    return AgentCard(
        name="Agent Sentinel",
        description=(
            "Gemini-powered governance plane for enterprise AI agents. "
            "Sits between A2A peers and gates every task delegation against "
            "your policy. Records a hash-chained, HMAC-signed audit receipt "
            "for each delegation; emits a per-business-unit cost event."
        ),
        url=f"{base_url.rstrip('/')}/a2a/v1",
        version="0.1.0",
        provider={"organization": "Agent Sentinel", "url": base_url},
        capabilities=AgentCardCapabilities(
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=True,
        ),
        skills=[
            AgentSkill(
                id="governance.gate",
                name="Gate a task delegation",
                description=(
                    "Evaluate a proposed agent-to-agent task delegation "
                    "against company policy. Returns allow / deny / rewrite "
                    "with cited rationale and an audit receipt id."
                ),
                tags=["governance", "policy", "audit", "agent-to-agent"],
                examples=[
                    "Gate 'Sales agent delegates competitor analysis to Summary agent'.",
                    "Gate 'Finance agent delegates customer record processing to External Vendor agent'.",
                ],
            ),
            AgentSkill(
                id="audit.verify",
                name="Verify the audit ledger",
                description=(
                    "Walk the hash-chained receipt log and re-derive HMAC "
                    "signatures. Returns INTEGRITY: PASS or a list of tampered rows."
                ),
                tags=["audit", "integrity", "tamper-evidence"],
            ),
            AgentSkill(
                id="cost.meter",
                name="Per-BU cost rollup",
                description="Per-business-unit spend rollup for agent activity (base + Gemini split).",
                tags=["finance", "chargeback", "cost"],
            ),
        ],
    )


# ---- helpers -------------------------------------------------------------


def _intent_from_message(message: A2AMessage) -> str:
    """Best-effort summary of the task intent for use as the gated tool name."""
    for part in message.parts:
        if part.type == "text" and part.text:
            return part.text.strip().split("\n", 1)[0][:200]
    return "(no intent text)"


def _flatten_task_args(params: SentinelTaskSendParams) -> dict[str, Any]:
    """Turn the A2A task into a flat dict that the gating engines can match
    against (the static engine's regex checks look for PII / injection
    markers across all string-coerced values)."""
    text_blob = ""
    file_refs: list[str] = []
    data_blobs: list[dict[str, Any]] = []
    for part in params.message.parts:
        if part.type == "text" and part.text:
            text_blob += part.text + "\n"
        elif part.type == "file" and part.file:
            file_refs.append(str(part.file.get("name") or part.file.get("uri") or ""))
        elif part.type == "data" and part.data:
            data_blobs.append(part.data)
    return {
        "target_agent": params.target_agent,
        "session_id": params.sessionId or "",
        "message_text": text_blob.strip(),
        "files": file_refs,
        "data": data_blobs,
        "metadata": params.metadata,
        "intent": params.intent or _intent_from_message(params.message),
    }


async def _persist_task_metadata(task_id: str, receipt_id: str, decision: str) -> None:
    """Store the task->receipt linkage in a flat metadata table so
    /a2a/v1/tasks/{id} can return the gated task by id. We piggyback on
    the existing audit_receipts.session_id column — A2A task ids map
    1-to-1 with session_id."""
    # Nothing extra to persist — the audit receipt already carries
    # session_id == task.id, which is what we'll query by below.
    return None


# ---- routes --------------------------------------------------------------


@a2a_router.get("/.well-known/agent.json")
async def well_known_agent_card() -> dict[str, Any]:
    """A2A agent discovery — peer agents fetch this to learn what Sentinel offers."""
    return sentinel_agent_card().model_dump(exclude_none=True)


@a2a_router.post("/a2a/v1/tasks/send", response_model=A2ATask)
async def tasks_send(params: SentinelTaskSendParams) -> A2ATask:
    """Gate an A2A task delegation. Routes through the same pipeline as
    POST /v1/tools/call, with the virtual tool name
    `agent.delegate.<target_agent>` so receipts make the inter-agent
    handoff explicit."""
    # Lazy imports to avoid the same circular import we already navigated
    # for the agent runner.
    from sentinel.gateway.pipeline import gate_and_record, load_agent

    try:
        agent = await load_agent(params.sentinel_agent_id)
    except LookupError as e:
        raise HTTPException(404, str(e))

    task_id = params.id or _new_task_id()
    args = _flatten_task_args(params)

    call = ToolCallRequest(
        agent_id=agent.agent_id,
        session_id=task_id,  # so we can look up the receipt by task id later
        tool=f"agent.delegate.{params.target_agent}",
        args=args,
    )
    result = await gate_and_record(call, agent)

    decision = result.response.decision
    receipt_id = str(result.response.receipt_id)

    # Build the A2A response message.
    if decision == "deny":
        status = A2ATaskStatus(
            state="failed",
            message={
                "role": "agent",
                "parts": [{
                    "type": "text",
                    "text": (
                        f"BLOCKED by Sentinel: {result.response.rationale} "
                        f"(receipt {receipt_id})"
                    ),
                }],
            },
        )
        agent_reply = A2AMessage(
            role="agent",
            parts=[A2APart(type="text",
                text=f"BLOCKED by Sentinel governance: {result.response.rationale}")],
        )
    elif decision == "rewrite":
        rewritten = result.response.rewritten_args or args
        status = A2ATaskStatus(
            state="completed",
            message={
                "role": "agent",
                "parts": [{"type": "data", "data": rewritten}],
            },
        )
        agent_reply = A2AMessage(
            role="agent",
            parts=[A2APart(type="data", data=rewritten),
                   A2APart(type="text", text="Rewritten by Sentinel: PII redacted.")],
        )
    else:
        status = A2ATaskStatus(state="completed")
        agent_reply = A2AMessage(
            role="agent",
            parts=[A2APart(type="text", text=f"Approved by Sentinel (receipt {receipt_id}).")],
        )

    return A2ATask(
        id=task_id,
        sessionId=params.sessionId,
        status=status,
        history=[params.message, agent_reply],
        artifacts=[],
        metadata={
            "sentinel": {
                "receipt_id": receipt_id,
                "decision": decision,
                "decided_by": result.decided_by,
                "rationale": result.response.rationale,
                "cost_usd": result.response.cost_usd,
                "latency_ms": result.response.latency_ms,
                "target_agent": params.target_agent,
            },
        },
    )


@a2a_router.get("/a2a/v1/tasks/{task_id}", response_model=A2ATask)
async def tasks_get(task_id: str) -> A2ATask:
    """Look up a previously-gated A2A task by id. We resolve via the
    audit receipt whose session_id == task_id."""
    async with get_session() as s:
        row = (await s.execute(
            text(
                "SELECT receipt_id, decision, rationale, latency_ms, "
                "tool, args_hash, created_at "
                "FROM audit_receipts WHERE session_id = :s "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"s": task_id},
        )).mappings().first()
    if not row:
        raise HTTPException(404, f"No A2A task '{task_id}' found")

    state = "failed" if row["decision"] == "deny" else "completed"
    return A2ATask(
        id=task_id,
        status=A2ATaskStatus(state=state, timestamp=row["created_at"].isoformat()),
        history=[],
        metadata={
            "sentinel": {
                "receipt_id": str(row["receipt_id"]),
                "decision": row["decision"],
                "rationale": row["rationale"],
                "tool": row["tool"],
                "latency_ms": row["latency_ms"],
            },
        },
    )


# ---- internal --------------------------------------------------------------


def _new_task_id() -> str:
    from uuid import uuid4 as _uuid4
    return f"a2a-{_uuid4().hex[:12]}"
