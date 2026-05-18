"""Unit tests for the hash + HMAC computation that underpins the audit
ledger. We don't need a DB for these — the functions are pure."""
from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest

from sentinel.audit.ledger import _compute_self_hash, hash_args, sha256_hex
from sentinel.audit.ledger import ReceiptInput


def _make_input(**overrides) -> ReceiptInput:
    base: dict = dict(
        agent_id="agent-x", session_id="s-1", tool="web.search",
        args_hash=hash_args({"q": "test"}),
        decision="allow", decided_by="flash",
        confidence=0.9, escalated=False,
        rationale="ok", latency_ms=12,
    )
    base.update(overrides)
    return ReceiptInput(**base)


class TestHashArgs:
    def test_deterministic(self) -> None:
        a = hash_args({"q": "x", "y": 1})
        b = hash_args({"y": 1, "q": "x"})
        assert a == b
        assert len(a) == 64

    def test_different_args_different_hash(self) -> None:
        assert hash_args({"q": "a"}) != hash_args({"q": "b"})

    def test_handles_non_string_values(self) -> None:
        h = hash_args({"x": 1, "y": True, "z": [1, 2, 3]})
        assert len(h) == 64


class TestSelfHash:
    def test_deterministic_for_same_input(self) -> None:
        rid = uuid4()
        inp = _make_input()
        assert _compute_self_hash(rid, "prev1", inp) == _compute_self_hash(rid, "prev1", inp)

    def test_changes_when_rationale_changes(self) -> None:
        rid = uuid4()
        h1 = _compute_self_hash(rid, "p", _make_input(rationale="A"))
        h2 = _compute_self_hash(rid, "p", _make_input(rationale="B"))
        assert h1 != h2

    def test_changes_when_decision_changes(self) -> None:
        rid = uuid4()
        h1 = _compute_self_hash(rid, "p", _make_input(decision="allow"))
        h2 = _compute_self_hash(rid, "p", _make_input(decision="deny"))
        assert h1 != h2

    def test_changes_when_prev_hash_changes(self) -> None:
        rid = uuid4()
        inp = _make_input()
        assert _compute_self_hash(rid, "X", inp) != _compute_self_hash(rid, "Y", inp)

    def test_changes_when_receipt_id_changes(self) -> None:
        inp = _make_input()
        a = _compute_self_hash(uuid4(), "p", inp)
        b = _compute_self_hash(uuid4(), "p", inp)
        assert a != b

    def test_none_prev_hash_normalizes_to_empty(self) -> None:
        """A first receipt has prev_hash=None — internally that becomes ''."""
        rid = uuid4()
        inp = _make_input()
        h_none = _compute_self_hash(rid, None, inp)
        h_empty = _compute_self_hash(rid, "", inp)
        assert h_none == h_empty


class TestSha256Helper:
    def test_str_and_bytes_same_result(self) -> None:
        assert sha256_hex("abc") == sha256_hex(b"abc")

    def test_known_value(self) -> None:
        # SHA-256("abc") — canonical NIST test vector.
        assert sha256_hex("abc") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )
