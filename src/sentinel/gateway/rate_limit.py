"""Per-IP rate limiter for the expensive endpoints.

In-memory, sliding window, no Redis. Fine for a single-process Railway
deploy; for multi-replica you'd swap in Redis. The endpoints we protect
are the ones that hit Gemini (and therefore cost real money):

  POST /v1/tools/call
  POST /v1/agents/run
  POST /a2a/v1/tasks/send
  POST /v1/policies/upload       (Files API + caches.create)
  POST /v1/policies/text         (no Gemini, but used for spam-write protection)
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# Defaults aimed at: a curious tire-kicker gets a smooth experience; a
# scripted abuser hits the wall fast. Override via env on Railway.
DEFAULT_PER_MIN = int(os.environ.get("SENTINEL_RATE_LIMIT_PER_MIN", "30"))
DEFAULT_PER_DAY = int(os.environ.get("SENTINEL_RATE_LIMIT_PER_DAY", "500"))

# Endpoints that touch Gemini get the rate limit applied. Read-only
# endpoints (/v1/receipts, /v1/cost/rollup, etc.) are unlimited.
PROTECTED_PATHS = {
    "/v1/tools/call",
    "/v1/agents/run",
    "/a2a/v1/tasks/send",
    "/v1/policies/upload",
    "/v1/policies/text",
}


class _SlidingWindow:
    __slots__ = ("minute_hits", "day_hits", "per_min", "per_day")

    def __init__(self, per_min: int, per_day: int) -> None:
        self.minute_hits: dict[str, deque[float]] = defaultdict(deque)
        self.day_hits: dict[str, deque[float]] = defaultdict(deque)
        self.per_min = per_min
        self.per_day = per_day

    def hit(self, key: str) -> tuple[bool, int, int]:
        """Returns (allowed, remaining_minute, remaining_day)."""
        now = time.time()
        m = self.minute_hits[key]
        d = self.day_hits[key]

        # Evict expired entries.
        cutoff_min = now - 60
        while m and m[0] < cutoff_min:
            m.popleft()
        cutoff_day = now - 86400
        while d and d[0] < cutoff_day:
            d.popleft()

        if len(m) >= self.per_min:
            return False, 0, max(0, self.per_day - len(d))
        if len(d) >= self.per_day:
            return False, max(0, self.per_min - len(m)), 0

        m.append(now)
        d.append(now)
        return True, self.per_min - len(m), self.per_day - len(d)


_window = _SlidingWindow(DEFAULT_PER_MIN, DEFAULT_PER_DAY)


def _client_ip(request: Request) -> str:
    # Railway sets X-Forwarded-For; trust the leftmost entry.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "anon"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply the per-IP limit on PROTECTED_PATHS. Read-only endpoints
    bypass the limit so the dashboard's 2-second polling is never
    throttled."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if path not in PROTECTED_PATHS:
            return await call_next(request)

        ip = _client_ip(request)
        allowed, rem_min, rem_day = _window.hit(ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": (
                        f"Sentinel public-demo rate limit: "
                        f"{DEFAULT_PER_MIN}/min and {DEFAULT_PER_DAY}/day per IP. "
                        "Clone the repo and run locally for unlimited use: "
                        "github.com/SankarSubbayya/agent_sentinel"
                    ),
                    "remaining_minute": rem_min,
                    "remaining_day": rem_day,
                },
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining-Min"] = str(rem_min)
        response.headers["X-RateLimit-Remaining-Day"] = str(rem_day)
        return response
