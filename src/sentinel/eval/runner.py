"""Evaluation runner.

Runs every labeled case in cases.CASES against a running Sentinel gateway,
scores each response against the expected decision (and optionally decider
tier / escalate flag), and reports per-category accuracy and latency
percentiles."""
from __future__ import annotations

import asyncio
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx

from sentinel.eval.cases import CASES, Category, EvalCase


@dataclass(slots=True)
class EvalResult:
    case: EvalCase
    decision: str | None
    decided_by: str | None
    escalated: bool | None
    rationale: str | None
    latency_ms: int | None
    cost_usd: float | None
    correct: bool
    issues: list[str] = field(default_factory=list)
    http_status: int = 0


@dataclass(slots=True)
class CategoryStats:
    category: Category
    total: int
    correct: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    cost_total_usd: float
    by_tier: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class TierStats:
    tier: str
    calls: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    cost_total_usd: float


@dataclass(slots=True)
class EvalReport:
    total: int
    correct: int
    categories: list[CategoryStats]
    failures: list[EvalResult]
    tiers: list[TierStats]
    p50_ms: float
    p95_ms: float
    p99_ms: float
    cost_total_usd: float
    elapsed_s: float

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def _pct(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    return float(statistics.quantiles(values, n=100, method="inclusive")[int(q * 100) - 1])


def _percentiles(values: list[int]) -> tuple[float, float, float]:
    if len(values) < 3:
        v = float(values[0]) if values else 0.0
        return v, v, v
    return _pct(values, 0.50), _pct(values, 0.95), _pct(values, 0.99)


def _check_correctness(case: EvalCase, body: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    decision = body.get("decision")
    if decision not in case.all_acceptable:
        accepted = " | ".join(sorted(case.all_acceptable))
        issues.append(f"decision: expected {accepted}, got {decision!r}")

    # The /v1/tools/call response doesn't currently include decided_by /
    # escalated — pull those from the receipt query if the case asserts them.
    # For the baseline check we rely on what the response gives us:
    # decision is the primary signal. decided_by + escalate are checked in
    # a follow-up enrichment pass below (against /v1/receipts).

    return len(issues) == 0, issues


async def _enrich_with_receipt(
    client: httpx.AsyncClient, base_url: str, session_id: str
) -> dict[str, Any] | None:
    """Fetch the most recent receipt for a session_id to read decided_by /
    escalated which are not on the ToolCallResponse."""
    try:
        r = await client.get(
            f"{base_url}/v1/receipts",
            params={"limit": 5},
            timeout=8.0,
        )
        if r.status_code != 200:
            return None
        rows = r.json().get("receipts", [])
        # /v1/receipts doesn't filter by session_id; find by session match.
        for row in rows:
            # Quick match via tool + agent_id is too loose; we encoded
            # session_id="eval-<case.id>" so we can grep by it client-side
            # via a subsequent dedicated call. Postgres has the index on
            # session_id but the HTTP layer doesn't expose it as a filter
            # yet — we'll just match the most recent row.
            return row
    except Exception:
        return None
    return None


async def run_eval(
    sentinel_url: str = "http://127.0.0.1:8088",
    cases: list[EvalCase] | None = None,
    concurrency: int = 4,
) -> EvalReport:
    cases = cases if cases is not None else CASES
    t_start = time.perf_counter()
    sem = asyncio.Semaphore(concurrency)
    results: list[EvalResult] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        async def _one(case: EvalCase) -> EvalResult:
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.post(
                        f"{sentinel_url.rstrip('/')}/v1/tools/call",
                        json=case.envelope(),
                    )
                    body = r.json() if r.status_code == 200 else {}
                except Exception as e:
                    return EvalResult(
                        case=case,
                        decision=None,
                        decided_by=None,
                        escalated=None,
                        rationale=None,
                        latency_ms=int((time.perf_counter() - t0) * 1000),
                        cost_usd=None,
                        correct=False,
                        issues=[f"transport error: {e}"],
                        http_status=0,
                    )

                # Enrich with the receipt to get decided_by + escalated.
                receipt: dict[str, Any] | None = None
                try:
                    rid = body.get("receipt_id")
                    if rid:
                        rec = await client.get(
                            f"{sentinel_url.rstrip('/')}/v1/receipts",
                            params={"agent_id": case.agent_id, "limit": 5},
                            timeout=8.0,
                        )
                        if rec.status_code == 200:
                            for row in rec.json().get("receipts", []):
                                if row.get("receipt_id") == rid:
                                    receipt = row
                                    break
                except Exception:
                    pass

                decided_by = (receipt or {}).get("decided_by")
                escalated = (receipt or {}).get("escalated")

                ok, issues = _check_correctness(case, body)
                if case.expected_decided_by and decided_by and decided_by != case.expected_decided_by:
                    ok = False
                    issues.append(
                        f"decided_by: expected {case.expected_decided_by!r}, got {decided_by!r}"
                    )
                if case.expected_escalate is not None and escalated is not None:
                    if escalated != case.expected_escalate:
                        ok = False
                        issues.append(
                            f"escalated: expected {case.expected_escalate}, got {escalated}"
                        )

                return EvalResult(
                    case=case,
                    decision=body.get("decision"),
                    decided_by=decided_by,
                    escalated=escalated,
                    rationale=body.get("rationale"),
                    latency_ms=body.get("latency_ms"),
                    cost_usd=body.get("cost_usd"),
                    correct=ok,
                    issues=issues,
                    http_status=r.status_code,
                )

        results = await asyncio.gather(*(_one(c) for c in cases))

    # Aggregate
    by_cat: dict[Category, list[EvalResult]] = defaultdict(list)
    for r in results:
        by_cat[r.case.category].append(r)

    cat_stats: list[CategoryStats] = []
    for cat, items in by_cat.items():
        lats = [r.latency_ms for r in items if r.latency_ms is not None]
        p50, p95, p99 = _percentiles(lats)
        tier_counts: dict[str, int] = defaultdict(int)
        for r in items:
            tier_counts[r.decided_by or "unknown"] += 1
        cat_stats.append(
            CategoryStats(
                category=cat,
                total=len(items),
                correct=sum(1 for r in items if r.correct),
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                cost_total_usd=round(sum(r.cost_usd or 0 for r in items), 6),
                by_tier=dict(tier_counts),
            )
        )
    cat_stats.sort(key=lambda s: s.category)

    # Per-tier breakdown across all cases.
    by_tier: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        by_tier[r.decided_by or "unknown"].append(r)
    tier_stats: list[TierStats] = []
    for tier_name in ("static", "flash", "pro", "unknown"):
        items = by_tier.get(tier_name, [])
        if not items:
            continue
        lats = [r.latency_ms for r in items if r.latency_ms is not None]
        p50, p95, p99 = _percentiles(lats)
        tier_stats.append(
            TierStats(
                tier=tier_name,
                calls=len(items),
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                cost_total_usd=round(sum(r.cost_usd or 0 for r in items), 6),
            )
        )

    all_lats = [r.latency_ms for r in results if r.latency_ms is not None]
    p50, p95, p99 = _percentiles(all_lats)

    return EvalReport(
        total=len(results),
        correct=sum(1 for r in results if r.correct),
        categories=cat_stats,
        failures=[r for r in results if not r.correct],
        tiers=tier_stats,
        p50_ms=p50,
        p95_ms=p95,
        p99_ms=p99,
        cost_total_usd=round(sum(r.cost_usd or 0 for r in results), 6),
        elapsed_s=round(time.perf_counter() - t_start, 3),
    )


def format_report(report: EvalReport) -> str:
    lines: list[str] = []
    lines.append("Sentinel evaluation")
    lines.append(f"  total cases:   {report.total}")
    lines.append(
        f"  correct:       {report.correct} ({report.accuracy * 100:.1f}%)"
    )
    lines.append(f"  failures:      {len(report.failures)}")
    lines.append(
        f"  latency:       p50 {report.p50_ms:.0f}ms · p95 {report.p95_ms:.0f}ms · p99 {report.p99_ms:.0f}ms"
    )
    lines.append(f"  total cost:    ${report.cost_total_usd:.5f}")
    lines.append(f"  elapsed:       {report.elapsed_s}s")
    lines.append("")
    lines.append(f"{'Category':<28} {'Cases':>6} {'Correct':>8} {'Acc':>7} {'p50':>6} {'p95':>6} {'p99':>6} {'Spend':>10}")
    for s in report.categories:
        acc = (s.correct / s.total * 100) if s.total else 0
        lines.append(
            f"  {s.category:<26} {s.total:>6} {s.correct:>8} {acc:>6.1f}% "
            f"{s.p50_ms:>5.0f} {s.p95_ms:>5.0f} {s.p99_ms:>5.0f} ${s.cost_total_usd:>8.5f}"
        )

    if report.tiers:
        lines.append("")
        lines.append(f"{'Tier':<28} {'Calls':>6} {'%':>7} {'p50':>6} {'p95':>6} {'p99':>6} {'Spend':>10}")
        for t in report.tiers:
            pct = (t.calls / report.total * 100) if report.total else 0
            lines.append(
                f"  {t.tier:<26} {t.calls:>6} {pct:>6.1f}% "
                f"{t.p50_ms:>5.0f} {t.p95_ms:>5.0f} {t.p99_ms:>5.0f} ${t.cost_total_usd:>8.5f}"
            )

    if report.failures:
        lines.append("")
        lines.append("Failures:")
        for r in report.failures:
            lines.append(f"  [{r.case.category}] {r.case.id}")
            for issue in r.issues:
                lines.append(f"     → {issue}")
            if r.rationale:
                lines.append(f"     rationale: {r.rationale[:140]}")

    return "\n".join(lines)


# ---- Bench: latency stress test ----


@dataclass(slots=True)
class BenchReport:
    case_id: str
    iterations: int
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    p99_9_ms: float
    min_ms: int
    max_ms: int
    mean_ms: float
    total_cost_usd: float
    elapsed_s: float
    decisions: dict[str, int]
    tiers: dict[str, int]


async def run_bench(
    case: EvalCase,
    sentinel_url: str,
    iterations: int = 1000,
    concurrency: int = 16,
) -> BenchReport:
    """Hit the gateway N times with the same envelope to get reliable
    latency percentiles for a representative call."""
    t_start = time.perf_counter()
    sem = asyncio.Semaphore(concurrency)
    latencies: list[int] = []
    costs: list[float] = []
    decisions: dict[str, int] = defaultdict(int)
    tiers: dict[str, int] = defaultdict(int)

    async with httpx.AsyncClient(timeout=15.0) as client:
        async def _one(_: int) -> None:
            async with sem:
                try:
                    r = await client.post(
                        f"{sentinel_url.rstrip('/')}/v1/tools/call",
                        json={**case.envelope(), "session_id": f"bench-{case.id}"},
                    )
                    if r.status_code == 200:
                        b = r.json()
                        if isinstance(b.get("latency_ms"), int):
                            latencies.append(b["latency_ms"])
                        if isinstance(b.get("cost_usd"), (int, float)):
                            costs.append(float(b["cost_usd"]))
                        decisions[b.get("decision", "?")] += 1
                except Exception:
                    pass

        await asyncio.gather(*(_one(i) for i in range(iterations)))

    elapsed = round(time.perf_counter() - t_start, 3)
    if not latencies:
        latencies = [0]
    sorted_lat = sorted(latencies)
    p = lambda q: float(sorted_lat[min(len(sorted_lat) - 1, int(q * len(sorted_lat)))])

    return BenchReport(
        case_id=case.id,
        iterations=iterations,
        p50_ms=p(0.50),
        p90_ms=p(0.90),
        p95_ms=p(0.95),
        p99_ms=p(0.99),
        p99_9_ms=p(0.999),
        min_ms=min(latencies),
        max_ms=max(latencies),
        mean_ms=round(sum(latencies) / len(latencies), 2),
        total_cost_usd=round(sum(costs), 6),
        elapsed_s=elapsed,
        decisions=dict(decisions),
        tiers=dict(tiers),
    )


def format_bench(report: BenchReport) -> str:
    lines: list[str] = []
    lines.append(f"Sentinel bench · case {report.case_id} · {report.iterations} iterations")
    lines.append(f"  elapsed:   {report.elapsed_s}s ({report.iterations / report.elapsed_s:.1f} req/s effective)")
    lines.append(f"  total $:   ${report.total_cost_usd}")
    lines.append("")
    lines.append("  Latency (ms):")
    lines.append(f"    min   {report.min_ms}")
    lines.append(f"    p50   {report.p50_ms:.0f}")
    lines.append(f"    p90   {report.p90_ms:.0f}")
    lines.append(f"    p95   {report.p95_ms:.0f}")
    lines.append(f"    p99   {report.p99_ms:.0f}")
    lines.append(f"    p99.9 {report.p99_9_ms:.0f}")
    lines.append(f"    max   {report.max_ms}")
    lines.append(f"    mean  {report.mean_ms}")
    lines.append("")
    lines.append("  Decisions: " + ", ".join(f"{k}={v}" for k, v in report.decisions.items()))
    return "\n".join(lines)
