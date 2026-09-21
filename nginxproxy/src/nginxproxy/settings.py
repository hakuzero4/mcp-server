"""Environment-driven connection settings for Nginx Proxy Manager."""

from __future__ import annotations

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Connection settings loaded from `NPM_*` environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="NPM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    url: str = Field(
        default="http://127.0.0.1:81",
        validation_alias=AliasChoices("url", "base_url"),
        description="Nginx Proxy Manager admin URL. `/api` is appended if missing.",
    )
    email: str = Field(
        default="",
        validation_alias=AliasChoices("email", "identity"),
        description="Admin email used to request a JWT.",
    )
    password: str = Field(
        default="",
        validation_alias=AliasChoices("password", "secret"),
        description="Admin password used to request a JWT.",
    )
    token: str = Field(
        default="",
        description="Optional pre-issued Bearer token. Credentials are used if it expires.",
    )
    timeout: float = Field(default=30.0, description="Default HTTP timeout in seconds.")
    cert_timeout: float = Field(
        default=900.0,
        description="Timeout in seconds for Let's Encrypt issue and renew requests.",
    )

    @field_validator("url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        return value.strip().rstrip("/")
