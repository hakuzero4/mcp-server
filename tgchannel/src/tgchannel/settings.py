"""Environment-driven settings for the Telegram user client."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Credentials loaded from `TG_*` environment variables or `.env`.

    A blank `TG_API_ID` stays unset so the rest of the gateway can still start.
    """

    model_config = SettingsConfigDict(
        env_prefix="TG_",
        env_prefix_target="all",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    api_id: int = Field(default=0, description="App api_id from https://my.telegram.org.")
    api_hash: str = Field(default="", description="App api_hash from https://my.telegram.org.")
    session: str = Field(
        default="",
        description="Telethon string session from `python -m tgchannel.login`.",
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Seconds allowed for one Telegram tool call, including connect.",
    )
    store_path: str = Field(
        default="",
        description="SQLite file for saved channel posts. Empty disables only the archive tools.",
    )

    @field_validator("api_id", mode="before")
    @classmethod
    def blank_api_id(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return 0
        return value

    @field_validator("api_hash", "session", "store_path")
    @classmethod
    def strip_secret(cls, value: str) -> str:
        return value.strip()
