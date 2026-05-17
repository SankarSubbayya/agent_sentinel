"""The gating pipeline as a callable — usable from the HTTP handler AND the
agent runner without an HTTP self-call.

Static engine → drift signal → Flash gate → optional Pro escalation →
audit receipt → cost event. Returns a normalized ToolCallResponse plus the
internal decided_by tier so the agent runner can render it."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import text

from sentinel.audit import ReceiptInput, write_receipt
from sentinel.audit.ledger import fetch_recent_for_agent, hash_args
from sentinel.config import get_settings
from sentinel.cost import compute_cost, write_cost_event
from sentinel.db import get_session
from sentinel.gating import drift_signal, evaluate_static, flash_gate, pro_escalation
from sentinel.gating.static_engine import StaticVerdict
from sentinel.models import AgentRecord, ToolCallRequest, ToolCallResponse

log = structlog.get_logger()


@dataclass(slots=True)
class GatingResult:
    response: ToolCallResponse
    decided_by: str  # static | flash | pro
    escalated: bool
    policy_versions_used: list[dict[str, str]]
    gemini_cache_ids: list[str]


async def load_agent(agent_id: str) -> AgentRecord:
    async with get_session() as s:
        result = await s.execute(
            text(
                "SELECT agent_id, name, bu, role, declared_goal "
                "FROM agents WHERE agent_id = :a"
            ),
            {"a": agent_id},
        )
        row = result.mappings().first()
    if not row:
        raise LookupError(f"Unknown agent_id '{agent_id}'")
    return AgentRecord(**dict(row))


async def gate_and_record(call: ToolCallRequest, agent: AgentRecord) -> GatingResult:
    """Run the full pipeline on a single tool-call envelope. Persists a
    receipt + cost event regardless of outcome."""
    t0 = time.perf_counter()

    # 1) Static engine
    verdict: StaticVerdict = evaluate_static(call, agent)
    decided_by: str = "static"
    decision: str = verdict.decision  # "allow" | "deny" | "pass"
    confidence: float | None = None
    escalated = False
    rationale = verdict.rationale
    rewritten_args: dict[str, Any] | None = None
    policy_versions: list[dict[str, str]] = []
    cache_ids: list[str] = []

    recent = await fetch_recent_for_agent(agent.agent_id, limit=20)

    # 2) Drift signal
    drift_escalate, drift_reason = drift_signal(call, agent, recent)

    # 3) Flash gate
    if verdict.decision == "pass":
        gd = await flash_gate(call, agent)
        decided_by = "flash"
        decision = gd.decision
        confidence = gd.confidence
        escalated = gd.escalate or drift_escalate
        rationale = gd.rationale
        rewritten_args = gd.rewritten_args

        # 4) Pro escalation
        settings = get_settings()
        need_pro = (
            escalated
            or (confidence is not None and confidence < settings.flash_escalate_threshold)
        )
        if need_pro:
            pro_decision, pol_versions, cids = await pro_escalation(
                call, agent, recent, flash_decision=gd
            )
            decided_by = "pro"
            decision = pro_decision.decision
            confidence = pro_decision.confidence
            rationale = pro_decision.rationale
            rewritten_args = pro_decision.rewritten_args
            policy_versions = pol_versions
            cache_ids = cids
            if drift_reason:
                rationale = f"[drift:{drift_reason}] {rationale}"

    latency_ms = int((time.perf_counter() - t0) * 1000)

    # 5) Audit
    receipt_id = await write_receipt(
        ReceiptInput(
            agent_id=agent.agent_id,
            session_id=call.session_id,
            tool=call.tool,
            args_hash=hash_args(call.args),
            decision=decision,  # type: ignore[arg-type]
            decided_by=decided_by,  # type: ignore[arg-type]
            confidence=confidence,
            escalated=escalated,
            rationale=rationale,
            latency_ms=latency_ms,
            policy_versions_used=policy_versions,
            gemini_cache_ids=cache_ids,
        )
    )

    # 6) Cost
    base, gemini, total = compute_cost(decided_by, escalated, decision)
    await write_cost_event(
        receipt_id=receipt_id,
        bu=agent.bu,
        tool=call.tool,
        base_cost=base,
        gemini_cost=gemini,
        total_cost=total,
    )

    log.info(
        "sentinel.decision",
        agent=agent.agent_id,
        tool=call.tool,
        decision=decision,
        decided_by=decided_by,
        escalated=escalated,
        latency_ms=latency_ms,
        cost_usd=total,
    )

    return GatingResult(
        response=ToolCallResponse(
            decision=decision,  # type: ignore[arg-type]
            receipt_id=receipt_id,
            rationale=rationale,
            rewritten_args=rewritten_args,
            cost_usd=total,
            latency_ms=latency_ms,
        ),
        decided_by=decided_by,
        escalated=escalated,
        policy_versions_used=policy_versions,
        gemini_cache_ids=cache_ids,
    )
