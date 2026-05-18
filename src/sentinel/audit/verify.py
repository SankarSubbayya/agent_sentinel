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
from sentinel.kms import get_keyset


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


def _resolve_signing_key(row: dict[str, Any], legacy_key: str) -> str:
    """Look up the row's key_id in the keyset; fall back to legacy single-key."""
    key_id = row.get("key_id") or "k1"
    return get_keyset().get(key_id) or legacy_key


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

    # Resolve the right key for this receipt — supports rotated keys.
    actual_key = _resolve_signing_key(row, signing_key)
    expected_sig = _compute_signature(row["self_hash"], actual_key)
    signature_ok = expected_sig == row["signature"]
    if not signature_ok:
        issues.append(
            f"signature mismatch — HMAC under key_id={row.get('key_id') or 'k1'} does not match"
        )

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
    "signature, created_at, key_id"
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

    # Group by agent and walk each chain via prev_hash → self_hash links
    # rather than trusting timestamp order (Postgres `now()` shares a value
    # within a transaction, so multiple same-tx-time receipts can tie on
    # created_at and mislead a timestamp-based ordering).
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_agent.setdefault(r["agent_id"], []).append(r)

    tampered: list[ReceiptVerdict] = []
    chains: dict[str, dict[str, Any]] = {}
    verified = 0

    for aid, receipts in by_agent.items():
        # Build a self_hash → row map and a prev_hash → row map so we can
        # detect forks (two receipts pointing back to the same parent).
        by_self: dict[str, dict[str, Any]] = {}
        by_prev: dict[str | None, list[dict[str, Any]]] = {}
        for r in receipts:
            by_self[r["self_hash"]] = r
            by_prev.setdefault(r.get("prev_hash"), []).append(r)

        # Find the root: prev_hash is NULL (or missing).
        roots = by_prev.get(None, []) + by_prev.get("", [])

        ordered: list[dict[str, Any]] = []
        chain_ok = True
        chain_issues: list[str] = []

        if len(roots) > 1:
            chain_ok = False
            chain_issues.append(
                f"multiple chain roots ({len(roots)}) — fork detected before any receipt"
            )
            # Process them all in arrival order so the user sees each as tampered.
            ordered = list(receipts)
        elif not roots:
            chain_ok = False
            chain_issues.append("no chain root (no receipt with prev_hash IS NULL)")
            ordered = list(receipts)
        else:
            cur = roots[0]
            seen: set[str] = set()
            while cur is not None:
                if cur["self_hash"] in seen:
                    chain_ok = False
                    chain_issues.append(f"cycle detected at {cur['self_hash'][:16]}…")
                    break
                seen.add(cur["self_hash"])
                ordered.append(cur)
                # If multiple receipts list the same prev_hash, we have a fork.
                children = by_prev.get(cur["self_hash"], [])
                if len(children) > 1:
                    chain_ok = False
                    chain_issues.append(
                        f"fork at {cur['self_hash'][:16]}… — {len(children)} children"
                    )
                    # Continue with one child to surface the rest as siblings.
                    cur = children[0]
                elif len(children) == 1:
                    cur = children[0]
                else:
                    cur = None
            # Any receipt not reached via the walk is dangling.
            dangling = [r for r in receipts if r["self_hash"] not in seen]
            if dangling:
                chain_ok = False
                chain_issues.append(
                    f"{len(dangling)} receipt(s) not reachable from chain root"
                )
                ordered.extend(dangling)

        prev_self: str | None = None
        for row in ordered:
            verdict = verify_one(row, signing_key)
            expected_prev = row.get("prev_hash")
            # Normalize NULL/empty to the same sentinel.
            actual_prev = expected_prev or None
            if actual_prev != prev_self:
                verdict.chain_link_ok = False
                verdict.issues.append(
                    f"prev_hash mismatch — expected {(prev_self or '∅')[:16]}…, "
                    f"got {(actual_prev or '∅')[:16]}…"
                )
            if verdict.ok:
                verified += 1
            else:
                tampered.append(verdict)
            prev_self = row["self_hash"]

        chains[aid] = {
            "count": len(receipts),
            "ok": chain_ok and not any(
                not v.chain_link_ok for v in tampered if v.agent_id == aid
            ),
            "tail_self_hash": ordered[-1]["self_hash"] if ordered else None,
            "issues": chain_issues,
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
