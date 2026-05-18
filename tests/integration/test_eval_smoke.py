"""Lightweight integration test that runs a small subset of the eval
suite against the live gateway. Confirms the eval harness is wired
correctly and the headline categories pass."""
from __future__ import annotations

import os

import httpx
import pytest

from sentinel.eval.cases import CASES
from sentinel.eval.runner import run_eval


URL = os.environ.get("SENTINEL_TEST_URL", "http://127.0.0.1:8088")
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def alive() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{URL}/healthz")
        return r.status_code == 200
    except Exception:
        return False


def _subset(category: str) -> list:
    return [c for c in CASES if c.category == category]


class TestEvalSmoke:
    async def test_happy_path_subset_all_allow(self, alive: bool) -> None:
        if not alive:
            pytest.skip("gateway unreachable")
        cases = _subset("happy_path")
        assert cases, "no happy_path cases registered"
        report = await run_eval(sentinel_url=URL, cases=cases[:5], concurrency=2)
        assert report.correct == report.total, [
            (r.case.id, r.issues) for r in report.failures
        ]

    async def test_refund_cap_subset(self, alive: bool) -> None:
        if not alive:
            pytest.skip("gateway unreachable")
        cases = _subset("refund_cap")
        report = await run_eval(sentinel_url=URL, cases=cases, concurrency=2)
        assert report.correct == report.total

    async def test_role_escalation_subset(self, alive: bool) -> None:
        if not alive:
            pytest.skip("gateway unreachable")
        cases = _subset("role_escalation")
        report = await run_eval(sentinel_url=URL, cases=cases, concurrency=2)
        assert report.correct == report.total
