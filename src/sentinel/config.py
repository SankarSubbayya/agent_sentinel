"""Centralized settings loaded from .env. Imported by every other module."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    database_url: str = Field(..., alias="DATABASE_URL")
    sentinel_jwt_signing_key: str = Field(..., alias="SENTINEL_JWT_SIGNING_KEY")
    sentinel_host: str = Field("0.0.0.0", alias="SENTINEL_HOST")
    sentinel_port: int = Field(8080, alias="SENTINEL_PORT")

    flash_model: str = "gemini-2.5-flash"
    pro_model: str = "gemini-2.5-pro"

    # Synthetic rate card — based on Gemini list price, marked as such in the UI.
    base_tool_cost_usd: float = 0.0005
    flash_call_cost_usd: float = 0.00015
    pro_call_cost_usd: float = 0.0040

    # Confidence below which Flash escalates to Pro.
    flash_escalate_threshold: float = 0.85


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
