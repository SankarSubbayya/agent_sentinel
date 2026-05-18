"""Hash-chain + signature verifier for the audit ledger.

Reads receipts (from Postgres or a JSONL export), recomputes each receipt's
self_hash from canonical fields, re-derives the HMAC signature with the
Sentinel signing key, and checks that prev_hash links match the prior
receipt in the same agent's chain. Returns a structured report listing any
tampered, broken, or out-of-order rows.

This is the thing that backs the "tamper-evident audit trail" claim — an
external auditor with only the signing key can run this against a JSONL
export and prove the ledger has not been altered.

Usage:
    uv run sentinel ledger verify [--source db|jsonl] [--file FILE] [--agent ID]
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text

from sentinel.audit.ledger import sha256_hex
from sentinel.config import get_settings
from sentinel.db import get_session


# ---- Report shape ----


@dataclass(slots=True)
class ReceiptVerdict:
    receipt_id: str
    agent_id: str
    created_at: str
    self_hash_ok: bool
    signature_ok: bool
    chain_link_ok: bool
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.self_hash_ok and self.signature_ok and self.chain_link_ok


@dataclass(slots=True)
class VerifyReport:
    total: int
    verified: int
    tampered: list[ReceiptVerdict] = field(default_factory=list)
    chains: dict[str, dict[str, Any]] = field(default_factory=dict)
    # chains[agent_id] = {"count": N, "ok": bool, "tail_self_hash": str}

    @property
    def all_ok(self) -> bool:
        return self.verified == self.total and not self.tampered


# ---- Per-receipt recomputation ----


def _compute_self_hash(row: dict[str, Any]) -> str:
    """Re-derive self_hash from the canonical record. Must match write_receipt's
    layout in audit/ledger.py exactly — change one, change the other."""
    payload = json.dumps(
        {
            "id": str(row["receipt_id"]),
            "prev": row["prev_hash"] or "",
            "agent": row["agent_id"],
            "session": row["session_id"],
            "tool": row["tool"],
            "args_hash": row["args_hash"],
            "decision": row["decision"],
            "decided_by": row["decided_by"],
            "rationale_hash": sha256_hex(row["rationale"]),
            "policies": row["policy_versions_used"],
            "caches": row["gemini_cache_ids"],
        },
        sort_keys=True,
    )
    return sha256_hex(payload)


def _compute_signature(self_hash: str, signing_key: str) -> str:
    return hmac.new(
        signing_key.encode("utf-8"),
        self_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_one(row: dict[str, Any], signing_key: str) -> ReceiptVerdict:
    """Verify a single receipt record in isolation (self_hash + signature).
    Chain-link verification is done at the chain level, not here."""
    issues: list[str] = []
    expected_self_hash = _compute_self_hash(row)
    self_hash_ok = expected_self_hash == row["self_hash"]
    if not self_hash_ok:
        issues.append(
            f"self_hash mismatch — recomputed {expected_self_hash[:16]}…, "
            f"stored {str(row['self_hash'])[:16]}…"
        )

    expected_sig = _compute_signature(row["self_hash"], signing_key)
    signature_ok = expected_sig == row["signature"]
    if not signature_ok:
        issues.append("signature mismatch — HMAC over self_hash does not match")

    return ReceiptVerdict(
        receipt_id=str(row["receipt_id"]),
        agent_id=row["agent_id"],
        created_at=str(row["created_at"]),
        self_hash_ok=self_hash_ok,
        signature_ok=signature_ok,
        chain_link_ok=True,  # set per-chain below
        issues=issues,
    )


# ---- Sources: DB and JSONL ----


_RECEIPT_COLS = (
    "receipt_id, agent_id, session_id, tool, args_hash, decision, decided_by, "
    "rationale, policy_versions_used, gemini_cache_ids, prev_hash, self_hash, "
    "signature, created_at"
)


async def _load_from_db(agent_id: str | None) -> list[dict[str, Any]]:
    sql = f"SELECT {_RECEIPT_COLS} FROM audit_receipts"
    params: dict[str, Any] = {}
    if agent_id:
        sql += " WHERE agent_id = :a"
        params["a"] = agent_id
    sql += " ORDER BY agent_id, created_at, receipt_id"
    async with get_session() as s:
        result = await s.execute(text(sql), params)
        return [dict(r) for r in result.mappings().all()]


def _load_from_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    # JSONL export may be reverse-chronological; sort canonically.
    out.sort(key=lambda r: (r.get("agent_id", ""), r.get("created_at", "")))
    return out


# ---- Top-level verify ----


async def verify(
    source: Literal["db", "jsonl"] = "db",
    jsonl_path: Path | None = None,
    agent_id: str | None = None,
) -> VerifyReport:
    if source == "db":
        rows = await _load_from_db(agent_id)
    else:
        if jsonl_path is None:
            raise ValueError("source='jsonl' requires jsonl_path")
        rows = _load_from_jsonl(jsonl_path)
        if agent_id:
            rows = [r for r in rows if r.get("agent_id") == agent_id]

    signing_key = get_settings().sentinel_jwt_signing_key

    # Group by agent so we can verify the per-agent hash chain.
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_agent.setdefault(r["agent_id"], []).append(r)

    tampered: list[ReceiptVerdict] = []
    chains: dict[str, dict[str, Any]] = {}
    verified = 0

    for aid, chain in by_agent.items():
        prev_hash: str | None = None
        chain_ok = True
        for row in chain:
            verdict = verify_one(row, signing_key)
            expected_prev = row["prev_hash"]
            if expected_prev != prev_hash:
                verdict.chain_link_ok = False
                verdict.issues.append(
                    f"prev_hash mismatch — expected {(prev_hash or '∅')[:16]}…, "
                    f"got {(expected_prev or '∅')[:16]}…"
                )
            if verdict.ok:
                verified += 1
            else:
                tampered.append(verdict)
                chain_ok = False
            prev_hash = row["self_hash"]
        chains[aid] = {
            "count": len(chain),
            "ok": chain_ok,
            "tail_self_hash": chain[-1]["self_hash"] if chain else None,
        }

    return VerifyReport(
        total=len(rows),
        verified=verified,
        tampered=tampered,
        chains=chains,
    )


def format_report(report: VerifyReport) -> str:
    """Human-readable summary for the CLI."""
    lines: list[str] = []
    lines.append(f"Audit ledger verification")
    lines.append(f"  total receipts:  {report.total}")
    lines.append(f"  verified:        {report.verified}")
    lines.append(f"  tampered:        {len(report.tampered)}")
    lines.append("")
    lines.append(f"Chains: {len(report.chains)} agent(s)")
    for aid, info in report.chains.items():
        marker = "OK" if info["ok"] else "BROKEN"
        tail = (info["tail_self_hash"] or "")[:16] + ("…" if info["tail_self_hash"] else "")
        lines.append(f"  [{marker:<6}] {aid:<24} {info['count']:>4} receipts  tail={tail}")

    if report.tampered:
        lines.append("")
        lines.append("Tampered receipts:")
        for v in report.tampered[:20]:
            lines.append(f"  {v.receipt_id} ({v.agent_id})")
            for issue in v.issues:
                lines.append(f"     → {issue}")
        if len(report.tampered) > 20:
            lines.append(f"  … and {len(report.tampered) - 20} more")

    lines.append("")
    if report.all_ok:
        lines.append("INTEGRITY: PASS")
    else:
        lines.append("INTEGRITY: FAIL")
    return "\n".join(lines)
