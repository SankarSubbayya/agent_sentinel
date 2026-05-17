"""Gemini 2.5 Flash multimodal: PDF -> sections + domain tags + summary.

Returns a PolicyDoc ready for the catalog. Tags are constrained to a small
controlled vocabulary so the loader can do a strict overlap match."""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from sentinel.config import get_settings
from sentinel.policy_pipe.catalog import PolicyDoc


DOMAIN_TAGS = Literal[
    "PII",          # personal data, customer records
    "financial",    # refund, payment, ledger
    "vendor",       # third-party recipient rules
    "security",     # auth, secrets, access
    "export",       # cross-border / external transfer
    "retention",    # data lifecycle
    "marketing",    # outreach, opt-in/out
]


class ExtractedPolicy(BaseModel):
    name: str = Field(..., description="Document title (e.g. 'Data Handling Policy').")
    version: str = Field(..., description="Version tag, e.g. 'v3.2' or '2026.05'.")
    effective_date: str | None = Field(
        None, description="ISO YYYY-MM-DD or null if unknown."
    )
    summary: str = Field(..., description="<=80 word summary.")
    domain_tags: list[str] = Field(
        default_factory=list,
        description=f"Subset of {list(DOMAIN_TAGS.__args__)}. At least one.",
    )


_SYSTEM = (
    "You extract structured metadata from corporate policy documents. "
    "Choose tags conservatively from the allowed vocabulary. "
    "Output only the ExtractedPolicy schema."
)

_client: genai.Client | None = None


def _client_singleton() -> genai.Client:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY required for PolicyPipe.extractor")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


async def extract_pdf(path: Path) -> PolicyDoc:
    settings = get_settings()
    client = _client_singleton()
    pdf_bytes = path.read_bytes()
    resp = await client.aio.models.generate_content(
        model=settings.flash_model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            "Extract the metadata.",
        ],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            response_mime_type="application/json",
            response_schema=ExtractedPolicy,
            temperature=0.0,
        ),
    )
    parsed: ExtractedPolicy = resp.parsed  # type: ignore[assignment]
    eff: date | None = None
    if parsed.effective_date:
        try:
            eff = date.fromisoformat(parsed.effective_date)
        except ValueError:
            eff = None
    return PolicyDoc(
        id=None,
        name=parsed.name,
        version=parsed.version,
        effective_date=eff,
        domain_tags=parsed.domain_tags,
        summary=parsed.summary,
        source_sha256=_sha256_file(path),
    )
