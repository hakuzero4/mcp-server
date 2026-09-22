"""Environment-driven connection settings for quark-auto-save."""

from __future__ import annotations

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Connection settings loaded from `QAS_*` environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="QAS_",
        env_prefix_target="all",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    url: str = Field(
        default="http://127.0.0.1:5005",
        validation_alias=AliasChoices("url", "base_url"),
        description="quark-auto-save WebUI address, for example http://127.0.0.1:5005.",
    )
    username: str = Field(
        default="",
        validation_alias=AliasChoices("username", "user"),
        description="WebUI login name, the same account used at /login.",
    )
    password: str = Field(
        default="",
        description="WebUI login password.",
    )
    timeout: float = Field(default=60.0, description="HTTP timeout in seconds for ordinary API calls.")
    run_timeout: float = Field(
        default=900.0,
        description="Timeout in seconds for a transfer run. quark-auto-save itself defaults to 1800.",
    )

    @field_validator("url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        if not cleaned:
            raise ValueError("QAS URL is empty")
        return cleaned

    @field_validator("username", "password")
    @classmethod
    def strip_credential(cls, value: str) -> str:
        return value.strip()
