"""Unit tests for the Merkle-root construction in anchoring.py.

The on-chain anchoring integration is exercised in tests/integration/."""
from __future__ import annotations

import hashlib

import pytest

from sentinel.anchoring import merkle_root_hex


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _double(left_hex: str, right_hex: str) -> str:
    h = hashlib.sha256()
    h.update(bytes.fromhex(left_hex))
    h.update(bytes.fromhex(right_hex))
    return h.hexdigest()


class TestMerkleRoot:
    def test_empty_returns_zero_root(self) -> None:
        assert merkle_root_hex([]) == "0" * 64

    def test_single_leaf_is_leaf(self) -> None:
        leaf = _h("only-receipt")
        assert merkle_root_hex([leaf]) == leaf

    def test_two_leaves_known(self) -> None:
        a, b = _h("A"), _h("B")
        assert merkle_root_hex([a, b]) == _double(a, b)

    def test_three_leaves_pads_to_four(self) -> None:
        """Odd count: rightmost is duplicated at the layer it becomes orphan."""
        a, b, c = _h("A"), _h("B"), _h("C")
        # Layer 1: [hash(a||b), hash(c||c)]
        layer1 = [_double(a, b), _double(c, c)]
        expected = _double(layer1[0], layer1[1])
        assert merkle_root_hex([a, b, c]) == expected

    def test_four_leaves_balanced(self) -> None:
        a, b, c, d = _h("A"), _h("B"), _h("C"), _h("D")
        l1, r1 = _double(a, b), _double(c, d)
        expected = _double(l1, r1)
        assert merkle_root_hex([a, b, c, d]) == expected

    def test_deterministic(self) -> None:
        leaves = [_h(f"r{i}") for i in range(7)]
        assert merkle_root_hex(leaves) == merkle_root_hex(leaves)

    def test_order_matters(self) -> None:
        leaves = [_h(f"r{i}") for i in range(5)]
        assert merkle_root_hex(leaves) != merkle_root_hex(list(reversed(leaves)))

    def test_one_bit_change_in_leaf_changes_root(self) -> None:
        original = [_h(f"r{i}") for i in range(6)]
        tampered = list(original)
        # Flip one character in the middle of leaf #3
        tampered[3] = tampered[3][:-1] + ("0" if tampered[3][-1] != "0" else "1")
        assert merkle_root_hex(original) != merkle_root_hex(tampered)


class TestRootHexFormat:
    def test_output_is_64_hex_chars(self) -> None:
        out = merkle_root_hex([_h("x")])
        assert len(out) == 64
        int(out, 16)  # parses cleanly as hex
