"""Unit tests for KMS / key rotation."""
from __future__ import annotations

import json
import os

import pytest

from sentinel.kms import KeySet, get_keyset, reset_cache


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with a clean env + cleared keyset cache."""
    monkeypatch.delenv("SENTINEL_SIGNING_KEYS", raising=False)
    monkeypatch.delenv("SENTINEL_ACTIVE_KEY_ID", raising=False)
    monkeypatch.delenv("SENTINEL_JWT_SIGNING_KEY", raising=False)
    reset_cache()
    yield
    reset_cache()


class TestLegacyKey:
    def test_legacy_env_key_becomes_k1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SENTINEL_JWT_SIGNING_KEY", "deadbeef")
        ks = get_keyset()
        assert ks.active_key_id == "k1"
        assert ks.get("k1") == "deadbeef"

    def test_missing_key_falls_back_to_dev_unsafe(self) -> None:
        ks = get_keyset()
        # Should not raise; uses the dev-unsafe-key fallback.
        assert ks.active_key_id == "k1"
        assert ks.get("k1") is not None


class TestRotation:
    def test_multi_key_with_active(self, monkeypatch: pytest.MonkeyPatch) -> None:
        keys = {"k1": "old-key-hex", "k2": "new-key-hex"}
        monkeypatch.setenv("SENTINEL_SIGNING_KEYS", json.dumps(keys))
        monkeypatch.setenv("SENTINEL_ACTIVE_KEY_ID", "k2")
        ks = get_keyset()
        assert ks.active_key_id == "k2"
        assert ks.get("k1") == "old-key-hex"
        assert ks.get("k2") == "new-key-hex"

    def test_default_active_is_lexicographically_last(self, monkeypatch: pytest.MonkeyPatch) -> None:
        keys = {"k1": "a", "k3": "c", "k2": "b"}
        monkeypatch.setenv("SENTINEL_SIGNING_KEYS", json.dumps(keys))
        ks = get_keyset()
        assert ks.active_key_id == "k3"

    def test_invalid_active_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SENTINEL_SIGNING_KEYS", json.dumps({"k1": "x"}))
        monkeypatch.setenv("SENTINEL_ACTIVE_KEY_ID", "k99")
        with pytest.raises(RuntimeError, match="not in SENTINEL_SIGNING_KEYS"):
            get_keyset()

    def test_malformed_json_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SENTINEL_SIGNING_KEYS", "not-json")
        with pytest.raises(RuntimeError, match="parse error"):
            get_keyset()

    def test_empty_dict_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SENTINEL_SIGNING_KEYS", "{}")
        with pytest.raises(RuntimeError, match="non-empty"):
            get_keyset()
