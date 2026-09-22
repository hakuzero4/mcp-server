"""Helpers shared by MCP tools."""

from __future__ import annotations

from typing import Any

from fastmcp import Context
from fastmcp.exceptions import ToolError

from quarksave.client import QasClient
from quarksave.exceptions import QasApiError, TaskError


def qas(ctx: Context) -> QasClient:
    """Return the lifespan-scoped quark-auto-save client."""
    context = ctx.lifespan_context
    if not isinstance(context, dict) or "qas" not in context:
        raise ToolError("quark-auto-save client is not initialized.")
    return context["qas"]


async def call(coro: Any) -> Any:
    """Run a client coroutine and convert API errors into ToolError."""
    try:
        return await coro
    except QasApiError as exc:
        raise ToolError(str(exc)) from exc


def checked(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a task helper and convert TaskError into ToolError."""
    try:
        return func(*args, **kwargs)
    except TaskError as exc:
        raise ToolError(str(exc)) from exc
