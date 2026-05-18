"""Unit tests for the adapters core (mock-stubbed gateway pipeline)."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from sentinel.adapters.core import GateOutcome, SentinelGate, gate_tool_call


@pytest.fixture
def fake_pipeline(monkeypatch: pytest.MonkeyPatch):
    """Replace gateway.pipeline with stubs so unit tests don't need a DB."""

    class StubAgent:
        agent_id = "agent-x"
        name = "x"
        bu = "TestBU"
        role = "ops"
        declared_goal = "test"

    class StubResp:
        decision = "allow"
        receipt_id = uuid4()
        rationale = "ok"
        rewritten_args = None
        cost_usd = 0.0
        latency_ms = 1

    class StubResult:
        response = StubResp()
        decided_by = "static"
        escalated = False
        policy_versions_used: list = []
        gemini_cache_ids: list = []

    captured: list[dict[str, Any]] = []

    async def fake_load(agent_id: str):
        return StubAgent()

    async def fake_gate(call, agent):
        captured.append({"tool": call.tool, "args": call.args, "agent_id": call.agent_id})
        return StubResult()

    # Patch the module-level import inside adapters.core (lazy-imported).
    import sentinel.gateway.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "load_agent", fake_load)
    monkeypatch.setattr(pipeline_mod, "gate_and_record", fake_gate)
    return captured


@pytest.mark.asyncio
async def test_gate_tool_call_returns_outcome(fake_pipeline) -> None:
    outcome = await gate_tool_call("agent-x", "web.search", {"q": "hi"})
    assert isinstance(outcome, GateOutcome)
    assert outcome.decision == "allow"
    assert outcome.allowed is True


@pytest.mark.asyncio
async def test_gate_records_call_envelope(fake_pipeline) -> None:
    await gate_tool_call("agent-x", "web.search", {"q": "hi"}, session_id="sess-99")
    assert len(fake_pipeline) == 1
    assert fake_pipeline[0]["tool"] == "web.search"
    assert fake_pipeline[0]["args"] == {"q": "hi"}


@pytest.mark.asyncio
async def test_sentinel_gate_check(fake_pipeline) -> None:
    gate = SentinelGate("agent-x")
    outcome = await gate.check("crm.read", {"customer_id": "C-1"})
    assert outcome.decision == "allow"
    assert outcome.receipt_id is not None
    assert fake_pipeline[0]["agent_id"] == "agent-x"


@pytest.mark.asyncio
async def test_session_id_propagates(fake_pipeline) -> None:
    gate = SentinelGate("agent-x", session_id="sess-fixed")
    await gate.check("web.search", {"q": "x"})
    await gate.check("web.search", {"q": "y"})
    # Both calls share the same session_id (stored as gate.session_id).
    assert gate.session_id == "sess-fixed"
