"""Async SQLAlchemy engine + session factory + schema bootstrap."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sentinel.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _normalize_dsn(dsn: str) -> str:
    # Accept either postgres:// or postgresql:// and rewrite to asyncpg.
    if dsn.startswith("postgresql+asyncpg://"):
        return dsn
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    if dsn.startswith("postgres://"):
        return dsn.replace("postgres://", "postgresql+asyncpg://", 1)
    return dsn


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            _normalize_dsn(settings.database_url),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session


async def init_schema() -> None:
    """Apply all sql/*.sql migrations in order. Each is idempotent — safe
    to re-run on startup. New migrations should be added as new files."""
    engine = get_engine()
    sql_dir = Path(__file__).resolve().parents[3] / "sql"
    files = sorted(p for p in sql_dir.glob("*.sql"))
    async with engine.begin() as conn:
        raw = await conn.get_raw_connection()
        for path in files:
            await raw.driver_connection.execute(path.read_text())
