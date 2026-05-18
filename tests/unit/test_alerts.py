"""Unit tests for the alerts module — pure payload construction.

The actual HTTP send is exercised in integration tests via a mock webhook."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from sentinel.alerts import _floor, _severity, _slack_payload, _teams_payload


class TestSeverity:
    def test_deny_higher_than_rewrite(self) -> None:
        assert _severity("deny") > _severity("rewrite")

    def test_rewrite_higher_than_allow(self) -> None:
        assert _severity("rewrite") > _severity("allow")

    def test_unknown_decision_is_zero(self) -> None:
        assert _severity("anything-else") == 0


class TestFloor:
    def test_default_floor_is_deny(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ALERT_MIN_DECISION", raising=False)
        assert _floor() == _severity("deny")

    def test_rewrite_floor_is_below_deny(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALERT_MIN_DECISION", "rewrite")
        assert _floor() == _severity("rewrite")
        assert _floor() < _severity("deny")


class TestSlackPayload:
    def test_includes_required_fields(self) -> None:
        rid = uuid4()
        p = _slack_payload(
            receipt_id=rid,
            agent_id="agent-ops-01",
            bu="CustomerOps",
            tool="refund.issue",
            decision="deny",
            rationale="prompt injection in memo",
            decided_by="pro",
        )
        assert p["text"].startswith("Sentinel DENY")
        attachment = p["attachments"][0]
        field_titles = {f["title"]: f["value"] for f in attachment["fields"]}
        assert field_titles["Agent"] == "agent-ops-01"
        assert field_titles["BU"] == "CustomerOps"
        assert field_titles["Tool"] == "refund.issue"
        assert field_titles["Tier"] == "pro"
        assert "prompt injection" in field_titles["Rationale"]
        assert str(rid) in field_titles["Receipt"]

    def test_color_per_decision(self) -> None:
        p_deny = _slack_payload(uuid4(), "a", "b", "t", "deny", "r", "flash")
        p_rewrite = _slack_payload(uuid4(), "a", "b", "t", "rewrite", "r", "flash")
        assert p_deny["attachments"][0]["color"] == "#dc2626"
        assert p_rewrite["attachments"][0]["color"] == "#f59e0b"

    def test_rationale_truncated(self) -> None:
        long = "x" * 1000
        p = _slack_payload(uuid4(), "a", "b", "t", "deny", long, "flash")
        rationale = next(f["value"] for f in p["attachments"][0]["fields"] if f["title"] == "Rationale")
        assert len(rationale) <= 600


class TestTeamsPayload:
    def test_minimal_card_shape(self) -> None:
        p = _teams_payload(uuid4(), "a", "b", "t", "deny", "r", "flash")
        assert p["@type"] == "MessageCard"
        assert p["title"].startswith("Sentinel DENY")
