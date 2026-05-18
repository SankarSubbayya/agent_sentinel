"""Slack / Teams webhook alerts for policy violations.

Fire-and-forget. The alert call must never block or fail the gating
response — Sentinel writes the alert outcome to `alert_events` so the
dashboard can show whether a notification was delivered.

Configuration:
  SLACK_WEBHOOK_URL  — Incoming Webhook URL (https://hooks.slack.com/...)
  TEAMS_WEBHOOK_URL  — Teams Incoming Webhook URL (optional)
  ALERT_MIN_DECISION — 'deny' (default) | 'rewrite' — minimum severity
"""
from __future__ import annotations

import asyncio
import os
from typing import Any
from uuid import UUID

import httpx
import structlog
from sqlalchemy import text

from sentinel.db import get_session

log = structlog.get_logger()


_DEFAULT_FLOOR = {"deny": 2, "rewrite": 1, "allow": 0}


def _severity(decision: str) -> int:
    return _DEFAULT_FLOOR.get(decision, 0)


def _floor() -> int:
    return _severity(os.environ.get("ALERT_MIN_DECISION", "deny").lower())


def _slack_url() -> str | None:
    u = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    return u or None


def _teams_url() -> str | None:
    u = os.environ.get("TEAMS_WEBHOOK_URL", "").strip()
    return u or None


def _slack_payload(
    receipt_id: UUID,
    agent_id: str,
    bu: str,
    tool: str,
    decision: str,
    rationale: str,
    decided_by: str,
) -> dict[str, Any]:
    color = {"deny": "#dc2626", "rewrite": "#f59e0b"}.get(decision, "#3b82f6")
    return {
        "text": f"Sentinel {decision.upper()} · {agent_id} · {tool}",
        "attachments": [
            {
                "color": color,
                "fields": [
                    {"title": "Agent", "value": agent_id, "short": True},
                    {"title": "BU", "value": bu, "short": True},
                    {"title": "Tool", "value": tool, "short": True},
                    {"title": "Tier", "value": decided_by, "short": True},
                    {"title": "Rationale", "value": rationale[:600], "short": False},
                    {"title": "Receipt", "value": str(receipt_id), "short": False},
                ],
            }
        ],
    }


def _teams_payload(*args, **kwargs) -> dict[str, Any]:
    # Teams Adaptive Card minimal — reuse the same text.
    p = _slack_payload(*args, **kwargs)
    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": p["text"],
        "title": p["text"],
        "text": p["attachments"][0]["fields"][-2]["value"],
    }


async def _post(url: str, payload: dict[str, Any]) -> tuple[bool, str | None]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(url, json=payload)
        return r.is_success, None if r.is_success else f"{r.status_code} {r.reason_phrase}"
    except Exception as e:
        return False, str(e)


async def _record_alert(
    receipt_id: UUID, target: str, sent_ok: bool, error: str | None
) -> None:
    async with get_session() as s:
        await s.execute(
            text(
                "INSERT INTO alert_events (receipt_id, target, sent_ok, error) "
                "VALUES (:r, :t, :ok, :e)"
            ),
            {"r": str(receipt_id), "t": target, "ok": sent_ok, "e": error},
        )
        await s.commit()


async def maybe_alert(
    receipt_id: UUID,
    agent_id: str,
    bu: str,
    tool: str,
    decision: str,
    rationale: str,
    decided_by: str,
) -> None:
    """Send a Slack/Teams alert if severity meets the floor and a webhook
    is configured. Never raises — records success/failure to alert_events."""
    if _severity(decision) < _floor():
        return

    targets: list[tuple[str, str, dict[str, Any]]] = []
    if (url := _slack_url()):
        targets.append((
            "slack", url,
            _slack_payload(receipt_id, agent_id, bu, tool, decision, rationale, decided_by),
        ))
    if (url := _teams_url()):
        targets.append((
            "teams", url,
            _teams_payload(receipt_id, agent_id, bu, tool, decision, rationale, decided_by),
        ))

    if not targets:
        return

    async def _one(target: str, url: str, payload: dict[str, Any]) -> None:
        ok, err = await _post(url, payload)
        log.info("sentinel.alert", target=target, ok=ok, error=err)
        try:
            await _record_alert(receipt_id, target, ok, err)
        except Exception as e:
            log.warning("sentinel.alert_record_failed", error=str(e))

    # Fire-and-forget — never block the gating response on alert delivery.
    await asyncio.gather(*(_one(t, u, p) for t, u, p in targets), return_exceptions=True)
