"""Periodic refresh of policy caches that are nearing TTL expiry.

Standalone callable so it can be wired into any scheduler (APScheduler,
systemd timer, cron). For the hackathon demo, call once at startup if there
are docs whose `cache_expires_at` is within the next 30 minutes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from sentinel.db import get_session
from sentinel.policy_pipe.cache_builder import refresh_cache_ttl


async def refresh_expiring(window_minutes: int = 30, new_ttl_seconds: int = 21_600) -> int:
    """Refresh every cache whose expiry is within `window_minutes`. Returns count refreshed."""
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=window_minutes)
    async with get_session() as s:
        result = await s.execute(
            text(
                """
                SELECT id, cache_id FROM policy_docs
                WHERE cache_id IS NOT NULL
                  AND superseded_by IS NULL
                  AND cache_expires_at <= :cutoff
                """
            ),
            {"cutoff": cutoff},
        )
        rows = result.mappings().all()

    refreshed = 0
    for r in rows:
        try:
            new_expires = await refresh_cache_ttl(r["cache_id"], ttl_seconds=new_ttl_seconds)
        except Exception:
            # Likely the cache was already deleted upstream — caller should re-ingest.
            continue
        async with get_session() as s:
            await s.execute(
                text("UPDATE policy_docs SET cache_expires_at = :exp WHERE id = :id"),
                {"exp": new_expires, "id": r["id"]},
            )
            await s.commit()
        refreshed += 1
    return refreshed
