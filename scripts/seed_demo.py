"""Post-deploy data seeder — populates the dashboard with realistic
demo traffic so judges hitting the public URL see a live-looking system.

Run via `railway run python scripts/seed_demo.py` after both services
are up, or include in a Railway one-shot job."""
from __future__ import annotations

import asyncio
import os
import sys

# Allow running from anywhere via `python scripts/seed_demo.py`.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scripts.load_generator import main as _load_main  # noqa: E402


SENTINEL_URL = os.environ.get("SENTINEL_URL", "http://127.0.0.1:8088")


async def _seed() -> int:
    # Override the load generator's hard-coded URL.
    import scripts.load_generator as lg
    lg.SENTINEL_URL = SENTINEL_URL

    print(f"Seeding demo traffic against {SENTINEL_URL}")
    rc = await _load_main(total=1000, concurrency=8)
    print("seed complete")
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(_seed()))
