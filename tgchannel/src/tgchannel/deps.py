"""Helpers shared by MCP tools."""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.exceptions import ToolError

from tgchannel.client import TgClient
from tgchannel.exceptions import RefError, TgApiError, TgConfigError


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
    except (TgApiError, TgConfigError, RefError) as exc:
        raise ToolError(str(exc)) from exc


def checked(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a reference helper and convert RefError into ToolError."""
    try:
        return func(*args, **kwargs)
    except RefError as exc:
        raise ToolError(str(exc)) from exc
