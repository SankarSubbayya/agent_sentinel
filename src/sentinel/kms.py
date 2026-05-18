"""Minimal in-process KMS — supports multiple signing keys identified by key_id.

Production deployments swap this for a real KMS (AWS KMS, GCP KMS, customer-
controlled HSM). The interface is the same: caller asks for the *current*
signing key when writing; caller asks for the key matching a *specific*
key_id when verifying.

Configuration (in priority order):
  1. SENTINEL_SIGNING_KEYS = JSON object {"k2": "hex…", "k3": "hex…"} +
     SENTINEL_ACTIVE_KEY_ID = "k3" (the current write-key)
  2. SENTINEL_JWT_SIGNING_KEY (legacy) — single key, assigned key_id="k1"

Receipts carry their `key_id` so the verifier picks the right HMAC key.
Rotating the key is a matter of:
  - Adding a new entry to SENTINEL_SIGNING_KEYS
  - Updating SENTINEL_ACTIVE_KEY_ID
  - Restarting the gateway
Old receipts continue to verify under their original key.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(slots=True, frozen=True)
class KeySet:
    keys: dict[str, str]          # key_id -> hex key
    active_key_id: str

    def get(self, key_id: str) -> str | None:
        return self.keys.get(key_id)

    def active(self) -> tuple[str, str]:
        return self.active_key_id, self.keys[self.active_key_id]


@lru_cache(maxsize=1)
def get_keyset() -> KeySet:
    raw = os.environ.get("SENTINEL_SIGNING_KEYS", "").strip()
    if raw:
        try:
            keys = json.loads(raw)
            if not isinstance(keys, dict) or not keys:
                raise ValueError("SENTINEL_SIGNING_KEYS must be a non-empty JSON object")
        except Exception as e:
            raise RuntimeError(f"SENTINEL_SIGNING_KEYS parse error: {e}") from e
        active = os.environ.get("SENTINEL_ACTIVE_KEY_ID", "").strip()
        if not active:
            active = sorted(keys.keys())[-1]
        if active not in keys:
            raise RuntimeError(f"SENTINEL_ACTIVE_KEY_ID '{active}' not in SENTINEL_SIGNING_KEYS")
        return KeySet(keys=dict(keys), active_key_id=active)

    # Legacy single-key path — pydantic-settings loads .env into its
    # own settings object, not os.environ, so we go through get_settings
    # first and only fall back to a hard-coded dev key as a last resort.
    legacy = os.environ.get("SENTINEL_JWT_SIGNING_KEY", "").strip()
    if not legacy:
        try:
            from sentinel.config import get_settings  # local import avoids cycle
            legacy = (get_settings().sentinel_jwt_signing_key or "").strip()
        except Exception:
            legacy = ""
    if not legacy:
        legacy = "dev-unsafe-key"
    return KeySet(keys={"k1": legacy}, active_key_id="k1")


def reset_cache() -> None:
    """Force a re-read of the env (call after rotating in-process)."""
    get_keyset.cache_clear()
