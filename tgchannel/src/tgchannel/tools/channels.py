"""Read-only tools for public Telegram channels."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from tgchannel.deps import call, checked, tg
from tgchannel.refs import (
    DEFAULT_LIMIT,
    parse_channel_ref,
    require_limit,
    require_offset,
    require_query,
)

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def get_channel(ctx: Context, channel: str) -> dict[str, Any]:
        """Get the public profile of a channel or public group.

        Args:
            channel: @username, t.me/name, t.me/s/name, or telegram.me/name.
        """
        username = checked(parse_channel_ref, channel)
        return await call(tg(ctx).get_channel(username))

    @mcp.tool(annotations=READ)
    async def list_messages(
        ctx: Context,
        channel: str,
        limit: int = DEFAULT_LIMIT,
        offset_id: int = 0,
    ) -> dict[str, Any]:
        """List recent public posts, newest first. Media files are not downloaded.

        Args:
            channel: @username or public t.me link.
            limit: How many posts to return, from 1 to 100. Default 20.
            offset_id: Skip this message id and anything newer. Zero starts at the newest post.
        """
        username = checked(parse_channel_ref, channel)
        bounded = checked(require_limit, limit)
        offset = checked(require_offset, offset_id)
        return await call(tg(ctx).list_messages(username, limit=bounded, offset_id=offset))

    @mcp.tool(annotations=READ)
    async def search_messages(
        ctx: Context,
        channel: str,
        query: str,
        limit: int = DEFAULT_LIMIT,
        offset_id: int = 0,
    ) -> dict[str, Any]:
        """Search posts inside one public channel. This does not search all of Telegram.

        Args:
            channel: @username or public t.me link.
            query: Text to search for in that channel.
            limit: How many posts to return, from 1 to 100. Default 20.
            offset_id: Skip this message id and anything newer.
        """
        username = checked(parse_channel_ref, channel)
        cleaned = checked(require_query, query)
        bounded = checked(require_limit, limit)
        offset = checked(require_offset, offset_id)
        return await call(
            tg(ctx).search_messages(username, query=cleaned, limit=bounded, offset_id=offset)
        )
