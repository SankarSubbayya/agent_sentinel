"""Per-call cost accounting + BU rollups.

Synthetic rate card based on Gemini list price — the dashboard surfaces a
'based on Gemini list price' footnote so judges know it's a rate model, not
billed dollars."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from sentinel.config import get_settings
from sentinel.db import get_session


def compute_cost(
    decided_by: str,
    escalated: bool,
    decision: str,
) -> tuple[float, float, float]:
    """Return (base_cost_usd, gemini_cost_usd, total_cost_usd)."""
    s = get_settings()
    base = s.base_tool_cost_usd if decision in {"allow", "rewrite"} else 0.0
    gemini = 0.0
    if decided_by == "flash":
        gemini = s.flash_call_cost_usd
    elif decided_by == "pro":
        # Pro escalations also paid for the prior Flash hop.
        gemini = s.flash_call_cost_usd + s.pro_call_cost_usd
    elif escalated:
        gemini = s.flash_call_cost_usd + s.pro_call_cost_usd
    return base, gemini, round(base + gemini, 6)


async def write_cost_event(
    receipt_id: UUID,
    bu: str,
    tool: str,
    base_cost: float,
    gemini_cost: float,
    total_cost: float,
) -> None:
    async with get_session() as s:
        await s.execute(
            text(
                """
                INSERT INTO cost_events (receipt_id, bu, tool, base_cost_usd, gemini_cost_usd, total_cost_usd)
                VALUES (:r, :bu, :t, :b, :g, :tot)
                """
            ),
            {
                "r": str(receipt_id),
                "bu": bu,
                "t": tool,
                "b": base_cost,
                "g": gemini_cost,
                "tot": total_cost,
            },
        )
        await s.commit()


async def bu_rollup(days: int = 7) -> list[dict[str, Any]]:
    """Per-BU spend over the trailing N days, with split by Gemini vs base."""
    sql = text(
        """
        SELECT bu,
               COUNT(*) AS calls,
               ROUND(SUM(base_cost_usd)::numeric, 4)   AS base_usd,
               ROUND(SUM(gemini_cost_usd)::numeric, 4) AS gemini_usd,
               ROUND(SUM(total_cost_usd)::numeric, 4)  AS total_usd
        FROM cost_events
        WHERE created_at > now() - make_interval(days => :d)
        GROUP BY bu
        ORDER BY total_usd DESC
        """
    )
    async with get_session() as s:
        result = await s.execute(sql, {"d": days})
        rows = result.mappings().all()
        # Coerce Decimal → float for JSON response.
        return [
            {
                "bu": r["bu"],
                "calls": int(r["calls"]),
                "base_usd": float(r["base_usd"] or 0),
                "gemini_usd": float(r["gemini_usd"] or 0),
                "total_usd": float(r["total_usd"] or 0),
            }
            for r in rows
        ]
