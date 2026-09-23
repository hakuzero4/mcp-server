"""Save and read public channel posts in the local archive."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from tgchannel.archive import Archive
from tgchannel.deps import archive, call, checked, tg
from tgchannel.exceptions import ArchiveError
from tgchannel.refs import (
    DEFAULT_LIMIT,
    parse_channel_ref,
    parse_saved_message,
    require_limit,
    require_offset,
    require_query,
    require_row_offset,
    save_targets,
)

LOCAL = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
SAVE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)


def _ready(database: Archive) -> Archive:
    try:
        database.ensure_configured()
    except ArchiveError as exc:
        raise ToolError(str(exc)) from exc
    return database


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=SAVE)
    async def save_messages(
        ctx: Context,
        channel: str | None = None,
        messages: list[str] | None = None,
        limit: int = DEFAULT_LIMIT,
        offset_id: int = 0,
    ) -> dict[str, Any]:
        """Save posts from a public channel. The same post overwrites one row.

        A channel link saves the recent page. A post link, a key like telegram:7,
        or `messages` saves only those posts and leaves other saved rows in place.
        Stored fields are username, id, date, edited, text, truncated, views, forwards,
        replies, pinned, media, file_name, grouped_id, author, action, and link.
        Media files are not downloaded.

        Args:
            channel: @username, a public channel link, or one post link such as https://t.me/telegram/7.
            messages: Post links or keys to save. When set, the recent page is not saved.
            limit: How many recent posts to save, from 1 to 100. Default 20. Ignored for specific posts.
            offset_id: Skip this message id and anything newer. Zero starts at the newest post.
        """
        targets = checked(save_targets, channel, messages)
        database = _ready(archive(ctx))
        if targets is None:
            username = checked(parse_channel_ref, channel or "")
            bounded = checked(require_limit, limit)
            offset = checked(require_offset, offset_id)
            page = await call(tg(ctx).list_messages(username, limit=bounded, offset_id=offset))
            return await call(database.save(page["username"], page["messages"]))
        grouped: dict[str, list[int]] = {}
        order: list[str] = []
        for username, message_id in targets:
            if username not in grouped:
                order.append(username)
                grouped[username] = []
            grouped[username].append(message_id)
        pages = []
        missing: list[str] = []
        for username in order:
            page = await call(tg(ctx).get_messages(username, grouped[username]))
            pages.append(page)
            missing.extend(page.get("missing") or [])
        inserted = updated = unchanged = 0
        keys: list[str] = []
        saved_name = order[0] if len(order) == 1 else ""
        for page in pages:
            if not page["messages"]:
                continue
            saved = await call(database.save(page["username"], page["messages"]))
            inserted += saved["inserted"]
            updated += saved["updated"]
            unchanged += saved["unchanged"]
            keys.extend(saved["keys"])
            if len(order) == 1:
                saved_name = saved["username"]
        result: dict[str, Any] = {
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "keys": keys,
            "missing": missing,
        }
        if saved_name:
            result["username"] = saved_name
        return result

    @mcp.tool(annotations=LOCAL)
    async def list_saved(
        ctx: Context,
        channel: str,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List posts already saved for one channel, newest first.

        Args:
            channel: @username or public t.me link.
            limit: How many saved posts to return, from 1 to 100. Default 20.
            offset: How many matching posts to skip, from 0 to 1000.
        """
        username = checked(parse_channel_ref, channel)
        bounded = checked(require_limit, limit)
        skipped = checked(require_row_offset, offset)
        database = _ready(archive(ctx))
        return await call(database.list_saved(username, limit=bounded, offset=skipped))

    @mcp.tool(annotations=LOCAL)
    async def count_saved(ctx: Context, channel: str) -> dict[str, Any]:
        """Count posts already saved for one channel.

        Args:
            channel: @username or public t.me link.
        """
        username = checked(parse_channel_ref, channel)
        database = _ready(archive(ctx))
        return await call(database.count_saved(username))

    @mcp.tool(annotations=LOCAL)
    async def search_saved(
        ctx: Context,
        channel: str,
        query: str,
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Search saved posts in one channel. The match is a literal substring.

        Args:
            channel: @username or public t.me link.
            query: Text to find. `%` and `_` are literal, not wildcards.
            limit: How many posts to return, from 1 to 100. Default 20.
        """
        username = checked(parse_channel_ref, channel)
        cleaned = checked(require_query, query)
        bounded = checked(require_limit, limit)
        database = _ready(archive(ctx))
        return await call(database.search_saved(username, cleaned, limit=bounded))

    @mcp.tool(annotations=LOCAL)
    async def get_saved(ctx: Context, message: str) -> dict[str, Any]:
        """Return one saved post, including its full text.

        Args:
            message: Saved key such as telegram:7, or a t.me message link.
        """
        username, message_id = checked(parse_saved_message, message)
        database = _ready(archive(ctx))
        return await call(database.get_saved(username, message_id))
