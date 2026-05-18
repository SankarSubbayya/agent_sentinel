"""Receipt anchoring — periodically compute a Merkle root over recent
receipt self_hashes and emit it as an `anchor_batch`. The root is the
single 32-byte commitment that an external party (auditor, customer,
on-chain contract) can store to prove the receipt log existed at a
given time.

Three targets supported:
  - 'local'           — write the root to a JSONL file (default)
  - 'opentimestamps'  — produce an OTS proof on demand (stubbed; emit
                         the root + a placeholder pointer for v1)
  - 'arc'             — Arc nanopayment-style on-chain anchor (stub —
                         this is where the user's Arc/Circle work plugs in)

Anchoring on a chain is intentionally optional. Most enterprises do not
need it; the HMAC-signed hash chain is already tamper-evident for any
auditor with the signing key. On-chain anchoring removes the need to
trust the signing key holder."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import text

from sentinel.db import get_session


Target = Literal["local", "opentimestamps", "arc"]


@dataclass(slots=True)
class AnchorResult:
    batch_id: UUID
    merkle_root: str
    receipt_count: int
    range_start_ts: datetime | None
    range_end_ts: datetime | None
    anchor_target: Target
    anchor_pointer: str


def _sha256(data: bytes) -> bytes:
    h = hashlib.sha256()
    h.update(data)
    return h.digest()


def merkle_root_hex(leaves: list[str]) -> str:
    """Compute a SHA-256 binary Merkle root over hex-string leaves.
    Odd nodes at any layer are duplicated (Bitcoin-style)."""
    if not leaves:
        return "0" * 64
    nodes = [bytes.fromhex(l) for l in leaves]
    while len(nodes) > 1:
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])
        nodes = [_sha256(nodes[i] + nodes[i + 1]) for i in range(0, len(nodes), 2)]
    return nodes[0].hex()


async def _pending_leaves() -> tuple[list[str], datetime | None, datetime | None]:
    """Receipts since the most recent anchor batch, ordered by created_at."""
    async with get_session() as s:
        last = (await s.execute(
            text("SELECT MAX(range_end_ts) FROM anchor_batches")
        )).scalar()
        if last is None:
            result = await s.execute(text(
                "SELECT self_hash, created_at FROM audit_receipts "
                "ORDER BY created_at, receipt_id"
            ))
        else:
            result = await s.execute(text(
                "SELECT self_hash, created_at FROM audit_receipts "
                "WHERE created_at > :since "
                "ORDER BY created_at, receipt_id"
            ), {"since": last})
        rows = result.all()
    leaves = [r[0] for r in rows]
    ts = [r[1] for r in rows]
    return leaves, (ts[0] if ts else None), (ts[-1] if ts else None)


async def _persist(
    batch_id: UUID,
    root: str,
    count: int,
    start_ts: datetime | None,
    end_ts: datetime | None,
    target: Target,
    pointer: str,
) -> None:
    async with get_session() as s:
        await s.execute(
            text(
                """
                INSERT INTO anchor_batches
                  (id, merkle_root, range_start_ts, range_end_ts,
                   receipt_count, anchor_target, anchor_pointer)
                VALUES (:id, :root, :s, :e, :n, :t, :p)
                """
            ),
            {"id": str(batch_id), "root": root, "s": start_ts, "e": end_ts,
             "n": count, "t": target, "p": pointer},
        )
        # Mark anchored receipts so we can show this in the UI.
        if start_ts and end_ts:
            await s.execute(
                text(
                    "UPDATE audit_receipts SET anchored_at = now() "
                    "WHERE created_at >= :s AND created_at <= :e"
                ),
                {"s": start_ts, "e": end_ts},
            )
        await s.commit()


def _emit_local(root: str, batch_id: UUID, count: int) -> str:
    path = Path(os.environ.get("ANCHOR_LOCAL_FILE", "anchor_log.jsonl"))
    payload = {
        "batch_id": str(batch_id),
        "merkle_root": root,
        "receipt_count": count,
        "emitted_at": datetime.utcnow().isoformat() + "Z",
    }
    with path.open("a") as f:
        f.write(json.dumps(payload) + "\n")
    return f"file://{path.resolve()}"


def _emit_opentimestamps(root: str) -> str:
    """OpenTimestamps anchoring stub. Real impl would call
    `opentimestamps-client` to produce an .ots proof against
    a public calendar. For the hackathon we emit a recoverable
    pointer that documents the intended target.

    Production drop-in: call `subprocess.run(['ots', 'stamp', root_file])`
    and store the .ots path in anchor_pointer."""
    return f"ots://stamp/{root}"


def _emit_arc(root: str) -> str:
    """Arc / Circle nanopayment-style anchoring stub. Connects to the
    user's prior work (ARC_DataPiper, Midstream). Real impl would post
    a tx to the Arc state channel with the root as data."""
    return f"arc://anchor/{root}"


async def anchor_pending(target: Target = "local") -> AnchorResult:
    """Compute the Merkle root over all unanchored receipts and emit."""
    leaves, start_ts, end_ts = await _pending_leaves()
    root = merkle_root_hex(leaves)
    batch_id = uuid4()

    if target == "opentimestamps":
        pointer = _emit_opentimestamps(root)
    elif target == "arc":
        pointer = _emit_arc(root)
    else:
        pointer = _emit_local(root, batch_id, len(leaves))

    if leaves:
        await _persist(batch_id, root, len(leaves), start_ts, end_ts, target, pointer)

    return AnchorResult(
        batch_id=batch_id,
        merkle_root=root,
        receipt_count=len(leaves),
        range_start_ts=start_ts,
        range_end_ts=end_ts,
        anchor_target=target,
        anchor_pointer=pointer,
    )


async def list_anchors(limit: int = 50) -> list[dict]:
    async with get_session() as s:
        result = await s.execute(
            text(
                "SELECT id, merkle_root, range_start_ts, range_end_ts, "
                "receipt_count, anchor_target, anchor_pointer, created_at "
                "FROM anchor_batches "
                "ORDER BY created_at DESC LIMIT :n"
            ),
            {"n": limit},
        )
        rows = result.mappings().all()
    return [
        {
            "id": str(r["id"]),
            "merkle_root": r["merkle_root"],
            "range_start_ts": r["range_start_ts"].isoformat() if r["range_start_ts"] else None,
            "range_end_ts": r["range_end_ts"].isoformat() if r["range_end_ts"] else None,
            "receipt_count": r["receipt_count"],
            "anchor_target": r["anchor_target"],
            "anchor_pointer": r["anchor_pointer"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
