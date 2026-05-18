"""Shared pytest fixtures.

The integration tests need a running Sentinel gateway at SENTINEL_TEST_URL
(default http://127.0.0.1:8088). Unit tests are pure-Python and have no
external dependencies.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio


SENTINEL_URL = os.environ.get("SENTINEL_TEST_URL", "http://127.0.0.1:8088")


@pytest.fixture(scope="session")
def sentinel_url() -> str:
    return SENTINEL_URL


@pytest_asyncio.fixture
async def gateway_alive(sentinel_url: str) -> bool:
    """Skip integration tests if the gateway isn't reachable."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{sentinel_url}/healthz")
            return r.status_code == 200
    except Exception:
        return False
