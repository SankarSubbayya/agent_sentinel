"""Pure-SQL CRUD over the `policy_docs` table.

PolicyPipe is the Gemini-native ingestion layer: extractor produces records,
cache_builder stamps cache IDs, loader hands cache IDs to the Pro escalation.
This module owns the persistence in between."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text

from sentinel.db import get_session


@dataclass(slots=True)
class PolicyDoc:
    id: UUID | None
    name: str
    version: str
    effective_date: date | None
    domain_tags: list[str] = field(default_factory=list)
    summary: str | None = None
    source_sha256: str = ""
    gemini_file_id: str | None = None
    cache_id: str | None = None
    cache_expires_at: datetime | None = None


async def insert_or_update_doc(doc: PolicyDoc) -> UUID:
    """Upsert by (name, version). Returns the row's UUID."""
    async with get_session() as s:
        result = await s.execute(
            text(
                """
                INSERT INTO policy_docs (
                    name, version, effective_date, domain_tags, summary, source_sha256
                ) VALUES (:n, :v, :e, :tags, :sum, :sha)
                ON CONFLICT (name, version) DO UPDATE SET
                    effective_date = EXCLUDED.effective_date,
                    domain_tags    = EXCLUDED.domain_tags,
                    summary        = EXCLUDED.summary,
                    source_sha256  = EXCLUDED.source_sha256
                RETURNING id
                """
            ),
            {
                "n": doc.name,
                "v": doc.version,
                "e": doc.effective_date,
                "tags": doc.domain_tags,
                "sum": doc.summary,
                "sha": doc.source_sha256,
            },
        )
        row = result.first()
        await s.commit()
        return UUID(str(row[0]))


async def set_cache(
    doc_id: UUID,
    gemini_file_id: str,
    cache_id: str,
    cache_expires_at: datetime,
) -> None:
    """Stamp Files API id + CachedContent name onto a policy row."""
    async with get_session() as s:
        await s.execute(
            text(
                """
                UPDATE policy_docs
                SET gemini_file_id = :f, cache_id = :c, cache_expires_at = :exp
                WHERE id = :id
                """
            ),
            {"f": gemini_file_id, "c": cache_id, "exp": cache_expires_at, "id": str(doc_id)},
        )
        await s.commit()


async def fetch_by_tags(tags: list[str]) -> list[dict[str, Any]]:
    """Return active (cache_id IS NOT NULL) policies whose domain_tags overlap `tags`."""
    if not tags:
        sql = text(
            "SELECT id, name, version, cache_id, domain_tags "
            "FROM policy_docs "
            "WHERE cache_id IS NOT NULL AND superseded_by IS NULL"
        )
        params: dict[str, Any] = {}
    else:
        sql = text(
            "SELECT id, name, version, cache_id, domain_tags "
            "FROM policy_docs "
            "WHERE cache_id IS NOT NULL AND superseded_by IS NULL "
            "AND domain_tags && :tags"
        )
        params = {"tags": tags}
    async with get_session() as s:
        result = await s.execute(sql, params)
        return [dict(r) for r in result.mappings().all()]


async def list_docs() -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT id, name, version, effective_date, domain_tags, summary,
               gemini_file_id, cache_id, cache_expires_at, created_at
        FROM policy_docs
        WHERE superseded_by IS NULL
        ORDER BY name, version DESC
        """
    )
    async with get_session() as s:
        result = await s.execute(sql)
        return [dict(r) for r in result.mappings().all()]
