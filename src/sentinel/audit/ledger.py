"""Hash-chained, signed audit receipts.

Each receipt's self_hash includes the prior receipt's self_hash for the same
agent, so the chain is tamper-evident: rewriting one row invalidates every
later row. The signature is HMAC-SHA256 with the Sentinel signing key —
verifiable by an external auditor given the key."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text

from sentinel.config import get_settings
from sentinel.db import get_session
from sentinel.kms import get_keyset


def sha256_hex(value: str | bytes) -> str:
    h = hashlib.sha256()
    h.update(value.encode("utf-8") if isinstance(value, str) else value)
    return h.hexdigest()


def hash_args(args: dict[str, Any]) -> str:
    # Canonical JSON for stable hashing.
    return sha256_hex(json.dumps(args, sort_keys=True, default=str))


def _hmac_sign(payload: str, key_id: str | None = None) -> tuple[str, str]:
    """Sign with either the active key (default) or a specific key_id (for
    re-deriving signatures during verification). Returns (key_id, sig_hex)."""
    keyset = get_keyset()
    if key_id is None:
        kid, key = keyset.active()
    else:
        key = keyset.get(key_id) or ""
        kid = key_id
    if not key:
        # Backstop for the unconfigured-env case (development only).
        key = get_settings().sentinel_jwt_signing_key or "dev-unsafe-key"
    sig = hmac.new(key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return kid, sig


@dataclass(slots=True)
class ReceiptInput:
    agent_id: str
    session_id: str
    tool: str
    args_hash: str
    decision: Literal["allow", "deny", "rewrite"]
    decided_by: Literal["static", "flash", "pro"]
    confidence: float | None
    escalated: bool
    rationale: str
    latency_ms: int
    policy_versions_used: list[dict[str, str]] = field(default_factory=list)
    gemini_cache_ids: list[str] = field(default_factory=list)
    gemini_trace_id: str | None = None
    observed_only: bool = False
    policy_conflict: bool = False


async def _prev_hash_for_agent(agent_id: str) -> str | None:
    async with get_session() as s:
        row = (
            await s.execute(
                text(
                    "SELECT self_hash FROM audit_receipts "
                    "WHERE agent_id = :a "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"a": agent_id},
            )
        ).first()
        return row[0] if row else None


async def _prev_hash_for_agent_in_session(s, agent_id: str) -> str | None:
    """Variant of _prev_hash_for_agent that runs inside the caller's open
    session — required when we hold a per-agent advisory lock and need the
    read + write to share a transaction."""
    row = (
        await s.execute(
            text(
                "SELECT self_hash FROM audit_receipts "
                "WHERE agent_id = :a "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"a": agent_id},
        )
    ).first()
    return row[0] if row else None


def _compute_self_hash(
    receipt_id: UUID, prev_hash: str | None, inp: ReceiptInput
) -> str:
    payload = json.dumps(
        {
            "id": str(receipt_id),
            "prev": prev_hash or "",
            "agent": inp.agent_id,
            "session": inp.session_id,
            "tool": inp.tool,
            "args_hash": inp.args_hash,
            "decision": inp.decision,
            "decided_by": inp.decided_by,
            "rationale_hash": sha256_hex(inp.rationale),
            "policies": inp.policy_versions_used,
            "caches": inp.gemini_cache_ids,
        },
        sort_keys=True,
    )
    return sha256_hex(payload)


async def write_receipt(inp: ReceiptInput) -> UUID:
    """Insert a new receipt; return its receipt_id. Hash-chain is per-agent.

    A Postgres advisory lock keyed on agent_id serializes concurrent writes
    for the same agent so the prev_hash → self_hash chain stays well-defined
    under load. Different agents continue to write in parallel; only same-
    agent writes block."""
    receipt_id = uuid4()
    rationale_hash = sha256_hex(inp.rationale)

    async with get_session() as s:
        # Per-agent advisory lock held for the duration of the transaction.
        # hashtext() bucketizes the string into a 32-bit signed int that
        # pg_advisory_xact_lock accepts.
        await s.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:a))"),
            {"a": inp.agent_id},
        )
        prev_hash = await _prev_hash_for_agent_in_session(s, inp.agent_id)
        self_hash = _compute_self_hash(receipt_id, prev_hash, inp)
        key_id, signature = _hmac_sign(self_hash)

        await s.execute(
            text(
                """
                INSERT INTO audit_receipts (
                    receipt_id, agent_id, session_id, tool, args_hash,
                    decision, decided_by, confidence, escalated,
                    rationale, rationale_hash,
                    policy_versions_used, gemini_cache_ids, gemini_trace_id,
                    prev_hash, self_hash, signature, latency_ms,
                    key_id, observed_only, policy_conflict
                ) VALUES (
                    :receipt_id, :agent_id, :session_id, :tool, :args_hash,
                    :decision, :decided_by, :confidence, :escalated,
                    :rationale, :rationale_hash,
                    CAST(:policies AS JSONB), :caches, :trace_id,
                    :prev_hash, :self_hash, :signature, :latency_ms,
                    :key_id, :observed_only, :policy_conflict
                )
                """
            ),
            {
                "receipt_id": str(receipt_id),
                "agent_id": inp.agent_id,
                "session_id": inp.session_id,
                "tool": inp.tool,
                "args_hash": inp.args_hash,
                "decision": inp.decision,
                "decided_by": inp.decided_by,
                "confidence": inp.confidence,
                "escalated": inp.escalated,
                "rationale": inp.rationale,
                "rationale_hash": rationale_hash,
                "policies": json.dumps(inp.policy_versions_used),
                "caches": inp.gemini_cache_ids,
                "trace_id": inp.gemini_trace_id,
                "prev_hash": prev_hash,
                "self_hash": self_hash,
                "signature": signature,
                "latency_ms": inp.latency_ms,
                "key_id": key_id,
                "observed_only": inp.observed_only,
                "policy_conflict": inp.policy_conflict,
            },
        )
        await s.commit()
    return receipt_id


async def query_receipts(
    agent_id: str | None = None,
    bu: str | None = None,
    tool: str | None = None,
    decision: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Filterable timeline query for the compliance view."""
    where = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if agent_id:
        where.append("ar.agent_id = :agent_id")
        params["agent_id"] = agent_id
    if bu:
        where.append("a.bu = :bu")
        params["bu"] = bu
    if tool:
        where.append("ar.tool = :tool")
        params["tool"] = tool
    if decision:
        where.append("ar.decision = :decision")
        params["decision"] = decision
    sql = f"""
        SELECT ar.receipt_id, ar.agent_id, a.bu, ar.tool, ar.decision,
               ar.decided_by, ar.escalated, ar.rationale, ar.latency_ms,
               ar.policy_versions_used, ar.created_at
        FROM audit_receipts ar
        JOIN agents a ON a.agent_id = ar.agent_id
        WHERE {' AND '.join(where)}
        ORDER BY ar.created_at DESC
        LIMIT :limit
    """
    async with get_session() as s:
        rows = (await s.execute(text(sql), params)).mappings().all()
        return [dict(r) for r in rows]


async def fetch_recent_for_agent(agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Used by drift detection to give Pro the agent's recent history."""
    sql = text(
        """
        SELECT tool, decision, rationale, created_at
        FROM audit_receipts
        WHERE agent_id = :a
        ORDER BY created_at DESC
        LIMIT :n
        """
    )
    async with get_session() as s:
        result = await s.execute(sql, {"a": agent_id, "n": limit})
        return [dict(r) for r in result.mappings().all()]
