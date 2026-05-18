"""Upload policy PDFs to Gemini Files API, wrap into a CachedContent.

Returns (gemini_file_id, cache_name, cache_expires_at). The Pro escalation
path passes `cached_content=cache_name` to skip ~75% of policy tokens."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from google import genai
from google.genai import types

from sentinel.config import get_settings

_client: genai.Client | None = None


def _client_singleton() -> genai.Client:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY required for PolicyPipe.cache_builder")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


_POLICY_SYSTEM = (
    "You are Sentinel's policy reasoner. Use ONLY the cached policy documents "
    "to justify decisions. Always cite the policy name and version you relied on."
)


async def build_cache_for_pdf(
    pdf_path: Path,
    display_name: str,
    ttl_seconds: int = 21_600,  # 6 hours
) -> tuple[str, str | None, datetime | None]:
    """Upload PDF, create CachedContent, return (file_id, cache_name, expires_at).

    Gemini's Cached Content has a 2,048-token minimum. Short policy PDFs
    (<2K tokens) will fail the cache create with INVALID_ARGUMENT. We
    keep the file upload (which always succeeds for any size) and return
    (file_id, None, None) so the Pro escalation path can still attach the
    file directly without caching. The catalog row records the file_id;
    the Pro reasoner falls back to passing the file inline."""
    settings = get_settings()
    client = _client_singleton()

    uploaded = await client.aio.files.upload(
        file=str(pdf_path),
        config={"mime_type": "application/pdf"},
    )

    try:
        cache = await client.aio.caches.create(
            model=settings.pro_model,
            config=types.CreateCachedContentConfig(
                display_name=f"sentinel:{display_name}",
                system_instruction=_POLICY_SYSTEM,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_uri(file_uri=uploaded.uri, mime_type="application/pdf")],
                    ),
                ],
                ttl=f"{ttl_seconds}s",
            ),
        )
    except Exception as e:
        # Most common: 400 INVALID_ARGUMENT 'Cached content is too small'.
        # We keep the file_id; Pro will attach the file inline at call time
        # instead of via cached_content. ~75% token savings only applies to
        # cached docs, so per-call cost goes up — flagged via NULL cache_id
        # in the policy_docs row so the CFO dashboard sees this.
        msg = str(e)
        if "too small" in msg or "min_total_token_count" in msg or "INVALID_ARGUMENT" in msg:
            return uploaded.name, None, None
        raise

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    return uploaded.name, cache.name, expires_at


async def refresh_cache_ttl(cache_name: str, ttl_seconds: int = 21_600) -> datetime:
    """Extend an existing cache's TTL without re-uploading the file."""
    client = _client_singleton()
    await client.aio.caches.update(
        name=cache_name,
        config=types.UpdateCachedContentConfig(ttl=f"{ttl_seconds}s"),
    )
    return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
