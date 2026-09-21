"""Helpers shared by MCP tools."""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.exceptions import ToolError

from nginxproxy.client import NpmClient
from nginxproxy.exceptions import NpmApiError


def npm(ctx: Context) -> NpmClient:
    """Return the lifespan-scoped NPM client."""
    context = ctx.lifespan_context
    if not isinstance(context, dict) or "npm" not in context:
        raise ToolError("Nginx Proxy Manager client is not initialized.")
    return context["npm"]


async def call(coro: Any) -> Any:
    """Run an NPM client coroutine and convert API errors into ToolError."""
    try:
        return await coro
    except NpmApiError as exc:
        raise ToolError(str(exc)) from exc
