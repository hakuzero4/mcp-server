"""Pydantic models for Nginx Proxy Manager tool arguments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ForwardScheme = Literal["http", "https"]
AccessDirective = Literal["allow", "deny"]


class ProxyLocation(BaseModel):
    """Custom location block on a proxy host."""

    path: str = Field(description="URL path this location matches, e.g. /api")
    forward_scheme: ForwardScheme = "http"
    forward_host: str
    forward_port: int = Field(ge=1, le=65535)
    forward_path: str | None = None
    advanced_config: str | None = None


class AccessItem(BaseModel):
    """HTTP basic-auth user on an access list."""

    username: str
    password: str


class AccessClient(BaseModel):
    """IP allow/deny rule on an access list."""

    address: str = Field(description="IP or CIDR, e.g. 192.168.1.0/24")
    directive: AccessDirective = "allow"


def compact(data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is None so NPM receives partial updates."""
    return {key: value for key, value in data.items() if value is not None}


def expand_param(expand: str | list[str] | None) -> str | None:
    if expand is None:
        return None
    if isinstance(expand, str):
        return expand
    return ",".join(expand)
