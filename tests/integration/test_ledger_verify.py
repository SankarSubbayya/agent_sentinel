"""Integration test for the audit-ledger verifier — via HTTP only.

Driving verify through `POST /v1/ledger/verify` (not via in-process
imports) keeps SQLAlchemy's async engine entirely in the gateway's
event loop and out of pytest-asyncio's per-test loops, which fixes the
'Future attached to a different loop' crash that hits in-process tests.

Flow:
  1. Truncate the ledger (test-only endpoint)
  2. Issue one tool call → 1 fresh receipt
  3. Verify → INTEGRITY: PASS
  4. Tamper one byte (test-only endpoint) → save original
  5. Verify → FAIL, identifies the tampered row
  6. Restore via re-tamper to original
  7. Verify → PASS again"""
from __future__ import annotations

import os
from uuid import uuid4

import httpx
import pytest


URL = os.environ.get("SENTINEL_TEST_URL", "http://127.0.0.1:8088")
pytestmark = pytest.mark.asyncio


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15.0)


@pytest.fixture
async def alive() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{URL}/healthz")
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def _truncate(alive: bool):
    """Wipe audit tables before each verify test for determinism."""
    if not alive:
        yield
        return
    async with httpx.AsyncClient(timeout=10.0) as c:
        await c.post(f"{URL}/v1/_test/truncate")
    yield


class TestVerify:
    async def test_clean_ledger_passes(self, alive: bool) -> None:
        if not alive:
            pytest.skip("gateway unreachable")
        async with httpx.AsyncClient(timeout=15.0) as c:
            # Seed one receipt.
            r = await c.post(f"{URL}/v1/tools/call", json={
                "agent_id": "agent-sales-01",
                "session_id": f"vt-{uuid4().hex[:8]}",
                "tool": "web.search",
                "args": {"q": "verify test"},
            })
            assert r.status_code == 200
            # Verify.
            v = await c.post(f"{URL}/v1/ledger/verify", json={})
        assert v.status_code == 200
        report = v.json()
        assert report["all_ok"] is True
        assert report["total"] >= 1
        assert not report["tampered"]

    async def test_byte_mutation_detected_and_restored(self, alive: bool) -> None:
        if not alive:
            pytest.skip("gateway unreachable")
        async with httpx.AsyncClient(timeout=15.0) as c:
            # Seed one receipt.
            r = await c.post(f"{URL}/v1/tools/call", json={
                "agent_id": "agent-sales-01",
                "session_id": f"vt-{uuid4().hex[:8]}",
                "tool": "web.search",
                "args": {"q": "verify test 2"},
            })
            receipt_id = r.json()["receipt_id"]

            # Tamper.
            t = await c.post(f"{URL}/v1/_test/tamper", json={
                "receipt_id": receipt_id,
                "rationale": "TAMPERED VALUE",
            })
            assert t.status_code == 200
            original_rationale = t.json()["original_rationale"]

            # Verify — should fail and flag this row.
            v = await c.post(f"{URL}/v1/ledger/verify", json={"agent_id": "agent-sales-01"})
            report = v.json()
            assert report["all_ok"] is False
            tampered_ids = {row["receipt_id"] for row in report["tampered"]}
            assert receipt_id in tampered_ids

            # Restore.
            await c.post(f"{URL}/v1/_test/tamper", json={
                "receipt_id": receipt_id,
                "rationale": original_rationale,
            })

            # Verify again — clean.
            v2 = await c.post(f"{URL}/v1/ledger/verify", json={"agent_id": "agent-sales-01"})
            report2 = v2.json()
            assert report2["all_ok"] is True

    async def test_verify_filters_by_agent(self, alive: bool) -> None:
        if not alive:
            pytest.skip("gateway unreachable")
        async with httpx.AsyncClient(timeout=15.0) as c:
            # Seed two different agents.
            await c.post(f"{URL}/v1/tools/call", json={
                "agent_id": "agent-sales-01",
                "session_id": f"vt-{uuid4().hex[:8]}",
                "tool": "web.search",
                "args": {"q": "sales"},
            })
            await c.post(f"{URL}/v1/tools/call", json={
                "agent_id": "agent-finance-01",
                "session_id": f"vt-{uuid4().hex[:8]}",
                "tool": "ledger.read",
                "args": {"period": "Q2"},
            })
            v_all = await c.post(f"{URL}/v1/ledger/verify", json={})
            v_sales = await c.post(f"{URL}/v1/ledger/verify", json={"agent_id": "agent-sales-01"})
        all_report = v_all.json()
        sales_report = v_sales.json()
        assert all_report["total"] >= 2
        assert sales_report["total"] == 1
        # Both should be intact.
        assert all_report["all_ok"] is True
        assert sales_report["all_ok"] is True
