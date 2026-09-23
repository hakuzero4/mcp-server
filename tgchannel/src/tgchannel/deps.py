"""Helpers shared by MCP tools."""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.exceptions import ToolError

from tgchannel.archive import Archive
from tgchannel.client import TgClient
from tgchannel.exceptions import ArchiveError, RefError, TgApiError, TgConfigError


def archive(ctx: Context) -> Archive:
    """Return the lifespan-scoped channel archive."""
    context = ctx.lifespan_context
    if not isinstance(context, dict) or "archive" not in context:
        raise ToolError("Channel archive is not initialized.")
    return context["archive"]


def tg(ctx: Context) -> TgClient:
    """Return the lifespan-scoped Telegram client."""
    context = ctx.lifespan_context
    if not isinstance(context, dict) or "tg" not in context:
        raise ToolError("Telegram client is not initialized.")
    return context["tg"]


async def call(coro: Any) -> Any:
    """Run a client coroutine and convert Telegram errors into ToolError."""
    try:
        return await coro
    except (TgApiError, TgConfigError, RefError, ArchiveError) as exc:
        raise ToolError(str(exc)) from exc


def checked(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a reference helper and convert RefError into ToolError."""
    try:
        return func(*args, **kwargs)
    except RefError as exc:
        raise ToolError(str(exc)) from exc
