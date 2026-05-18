"""A2A client adapter — gate outbound A2A delegations through Sentinel
before they reach the destination peer.

Usage:

    from sentinel.adapters.a2a_adapter import SentinelA2AClient

    client = SentinelA2AClient(
        sentinel_url="http://sentinel.internal/a2a/v1",
        sentinel_agent_id="agent-sales-01",
    )

    # Delegate a summarization task to the Summary peer agent.
    task = await client.delegate(
        target_agent="summary-agent",
        text="Summarize Q3 competitor pricing: Acme Pro $499/mo, Beta $429/mo, ...",
    )

    if task.status.state == "completed":
        # forward task to the real Summary peer with task.metadata["sentinel"]["receipt_id"]
        ...
    else:
        # task.status.message tells you why Sentinel blocked it
        ...

This adapter is for agents that prefer Pythonic helpers over raw HTTP.
For raw HTTP, agents POST directly to /a2a/v1/tasks/send."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from sentinel.a2a.models import A2AMessage, A2APart, A2ATask


@dataclass(slots=True)
class SentinelA2AClient:
    sentinel_url: str
    sentinel_agent_id: str
    session_id: str | None = None
    timeout: float = 15.0

    def __post_init__(self) -> None:
        self.sentinel_url = self.sentinel_url.rstrip("/")
        if self.session_id is None:
            self.session_id = f"a2a-sess-{uuid4().hex[:10]}"

    async def delegate(
        self,
        target_agent: str,
        text: str | None = None,
        data: dict[str, Any] | None = None,
        files: list[dict[str, Any]] | None = None,
        intent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> A2ATask:
        """Send a task to a target peer agent, gated by Sentinel."""
        parts: list[dict[str, Any]] = []
        if text:
            parts.append({"type": "text", "text": text})
        if data:
            parts.append({"type": "data", "data": data})
        if files:
            for f in files:
                parts.append({"type": "file", "file": f})
        if not parts:
            parts.append({"type": "text", "text": "(empty)"})

        payload = {
            "id": f"a2a-{uuid4().hex[:12]}",
            "sessionId": self.session_id,
            "sentinel_agent_id": self.sentinel_agent_id,
            "target_agent": target_agent,
            "intent": intent,
            "metadata": metadata or {},
            "message": {"role": "user", "parts": parts},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(f"{self.sentinel_url}/a2a/v1/tasks/send", json=payload)
        r.raise_for_status()
        return A2ATask.model_validate(r.json())

    async def get_task(self, task_id: str) -> A2ATask:
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(f"{self.sentinel_url}/a2a/v1/tasks/{task_id}")
        r.raise_for_status()
        return A2ATask.model_validate(r.json())

    async def discover(self) -> dict[str, Any]:
        """Fetch Sentinel's A2A agent card via .well-known."""
        root = self.sentinel_url.replace("/a2a/v1", "")
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(f"{root}/.well-known/agent.json")
        r.raise_for_status()
        return r.json()
