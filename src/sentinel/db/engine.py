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
    """Run sql/001_init.sql against the configured database. Idempotent."""
    engine = get_engine()
    schema_path = Path(__file__).resolve().parents[3] / "sql" / "001_init.sql"
    sql = schema_path.read_text()
    async with engine.begin() as conn:
        # asyncpg needs statements split — execute as one script via raw connection.
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute(sql)
