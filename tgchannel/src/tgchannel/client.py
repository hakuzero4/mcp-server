"""Read-only Telethon client for public channels.

The signed-in user is never told to join a channel. Flood waits are returned
to the caller; `flood_sleep_threshold=0` stops Telethon from sleeping on them.
"""

from __future__ import annotations

import asyncio
import struct
from typing import Any

from telethon import TelegramClient
from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    FloodWaitError,
    RPCError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetFullChannelRequest

from tgchannel.exceptions import RefError, TgApiError, TgConfigError, TgError
from tgchannel.refs import MAX_LIMIT, parse_channel_ref, require_limit, require_offset, require_query
from tgchannel.settings import Settings
from tgchannel.summarize import summarize_channel, summarize_message

_LOGIN = "Run: uv run python -m tgchannel.login"
_PRIVATE = (
    "This channel is private, or its history cannot be read until the account joins. "
    "This server does not join channels."
)


class TgClient:
    """Lazy Telegram connection. Nothing is opened until a tool asks for a channel."""

    def __init__(self, settings: Settings, telegram: Any | None = None) -> None:
        self.settings = settings
        self._telegram = telegram
        self._owned = telegram is None

    async def aclose(self) -> None:
        """Disconnect a client this instance opened. Injected clients are left alone."""
        if self._owned and self._telegram is not None:
            await _disconnect(self._telegram)
            self._telegram = None

    def redact(self, text: str) -> str:
        """Remove the session and api_hash if a library error quoted them."""
        redacted = text
        for secret in (self.settings.session, self.settings.api_hash):
            if secret:
                redacted = redacted.replace(secret, "[redacted]")
        return redacted

    async def get_channel(self, channel: str) -> dict[str, Any]:
        """Public profile: title, about, subscriber count, and link."""
        return await self._bounded(self._get_channel(channel))

    async def list_messages(
        self,
        channel: str,
        *,
        limit: int,
        offset_id: int = 0,
    ) -> dict[str, Any]:
        """Newest posts first. `offset_id` skips that message and everything newer."""
        return await self._bounded(
            self._messages(
                channel,
                limit=require_limit(limit),
                offset_id=require_offset(offset_id),
                query=None,
            )
        )

    async def get_messages(self, channel: str, message_ids: list[int]) -> dict[str, Any]:
        """Fetch specific posts by id. Missing ids are listed, not treated as an error."""
        if not isinstance(message_ids, list) or not message_ids or len(message_ids) > MAX_LIMIT:
            raise RefError("messages must contain 1 to 100 posts.")
        for message_id in message_ids:
            if isinstance(message_id, bool) or not isinstance(message_id, int) or message_id < 1:
                raise RefError("Message id must be a positive integer.")
        return await self._bounded(self._by_ids(channel, message_ids))

    async def search_messages(
        self,
        channel: str,
        *,
        query: str,
        limit: int,
        offset_id: int = 0,
    ) -> dict[str, Any]:
        """Search inside one public channel. This does not search all of Telegram."""
        return await self._bounded(
            self._messages(
                channel,
                limit=require_limit(limit),
                offset_id=require_offset(offset_id),
                query=require_query(query),
            )
        )

    async def _bounded(self, awaitable: Any) -> Any:
        try:
            return await asyncio.wait_for(awaitable, self.settings.timeout)
        except TimeoutError as exc:
            raise TgApiError(
                f"Telegram request timed out after {self.settings.timeout:g} seconds."
            ) from exc

    async def _get_channel(self, channel: str) -> dict[str, Any]:
        telegram, entity, username = await self._resolve(channel)
        try:
            full = await telegram(GetFullChannelRequest(entity))
        except (RPCError, ValueError, OSError) as exc:
            raise self._map(exc, username) from exc
        full_chat = getattr(full, "full_chat", None)
        return summarize_channel(
            channel_id=getattr(entity, "id", None),
            title=getattr(entity, "title", "") or "",
            username=username,
            kind=_channel_kind(entity),
            about=getattr(full_chat, "about", None),
            participants=getattr(full_chat, "participants_count", None),
        )

    async def _messages(
        self,
        channel: str,
        *,
        limit: int,
        offset_id: int,
        query: str | None,
    ) -> dict[str, Any]:
        telegram, entity, username = await self._resolve(channel)
        kwargs: dict[str, Any] = {"limit": limit}
        if offset_id:
            kwargs["offset_id"] = offset_id
        if query:
            kwargs["search"] = query
        items: list[dict[str, Any]] = []
        try:
            async for message in telegram.iter_messages(entity, **kwargs):
                items.append(summarize_message(message, username=username))
                if len(items) >= limit:
                    break
        except (RPCError, ValueError, OSError) as exc:
            raise self._map(exc, username) from exc
        return {
            "username": username,
            "title": getattr(entity, "title", "") or "",
            "kind": _channel_kind(entity),
            "messages": items,
        }

    async def _by_ids(self, channel: str, message_ids: list[int]) -> dict[str, Any]:
        telegram, entity, username = await self._resolve(channel)
        try:
            found = await telegram.get_messages(entity, ids=list(message_ids))
        except (RPCError, ValueError, OSError) as exc:
            raise self._map(exc, username) from exc
        if found is None:
            found_list: list[Any] = []
        elif isinstance(found, list):
            found_list = found
        else:
            found_list = [found]
        by_id: dict[int, dict[str, Any]] = {}
        for message in found_list:
            if message is None:
                continue
            message_id = getattr(message, "id", None)
            if isinstance(message_id, bool) or not isinstance(message_id, int):
                continue
            by_id[message_id] = summarize_message(message, username=username)
        name = username.lower()
        items: list[dict[str, Any]] = []
        missing: list[str] = []
        for message_id in message_ids:
            item = by_id.get(message_id)
            if item is None:
                missing.append(f"{name}:{message_id}")
                continue
            items.append(item)
        return {"username": username, "messages": items, "missing": missing}

    async def _resolve(self, channel: str) -> tuple[Any, Any, str]:
        username = parse_channel_ref(channel)
        telegram = await self._ensure()
        try:
            entity = await telegram.get_entity(username)
        except (RPCError, ValueError, OSError) as exc:
            raise self._map(exc, username) from exc
        kind = _entity_kind(entity)
        if kind == "user":
            raise TgApiError("This is a user account, not a public channel or group.")
        if kind == "chat":
            raise TgApiError("This chat has no public username.")
        if kind == "private":
            raise TgApiError(_PRIVATE)
        if kind != "channel":
            raise TgApiError(f"Not a public channel or group ({kind}).")
        public = _public_username(entity)
        if not public:
            raise TgApiError("This chat has no public username.")
        return telegram, entity, public

    async def _ensure(self) -> Any:
        if self._telegram is not None:
            return self._telegram
        if self.settings.api_id <= 0 or not self.settings.api_hash or not self.settings.session:
            raise TgConfigError(f"Set TG_API_ID, TG_API_HASH, and TG_SESSION. {_LOGIN}")
        try:
            client = self._open()
        except (ValueError, struct.error) as exc:
            raise TgConfigError(f"TG_SESSION is invalid. {_LOGIN}") from exc
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise TgConfigError(f"TG_SESSION is not logged in. {_LOGIN}")
        except TgError:
            await _disconnect(client)
            raise
        except (RPCError, ValueError, OSError) as exc:
            await _disconnect(client)
            raise TgApiError(self.redact(f"Telegram connection failed: {exc}")) from exc
        self._telegram = client
        return client

    def _open(self) -> TelegramClient:
        return TelegramClient(
            StringSession(self.settings.session),
            self.settings.api_id,
            self.settings.api_hash,
            timeout=self.settings.timeout,
            request_retries=2,
            connection_retries=2,
            retry_delay=1,
            flood_sleep_threshold=0,
            raise_last_call_error=True,
            receive_updates=False,
            device_model="mcp-server",
            app_version="tgchannel",
        )

    def _map(self, exc: Exception, username: str) -> TgError:
        if isinstance(exc, FloodWaitError):
            return TgApiError(f"Telegram rate limit. Retry after {exc.seconds} seconds.")
        if isinstance(exc, (UsernameInvalidError, UsernameNotOccupiedError)):
            return TgApiError(f"No public chat named @{username}.")
        if isinstance(exc, (ChannelPrivateError, ChannelInvalidError)):
            return TgApiError(_PRIVATE)
        if isinstance(exc, ValueError):
            lowered = str(exc).lower()
            if "username" in lowered or "cannot find" in lowered or "no user" in lowered:
                return TgApiError(f"No public chat named @{username}.")
        return TgApiError(self.redact(str(exc)))


def _entity_kind(entity: object) -> str:
    """Classify a Telethon entity by TL class name.

    The TL constructors change between layers, so tests use stand-ins with the same names
    instead of building a `Channel`.
    """
    name = type(entity).__name__
    if name == "User":
        return "user"
    if name in {"ChannelForbidden", "ChatForbidden"}:
        return "private"
    if name == "Chat":
        return "chat"
    if name == "Channel":
        return "channel"
    return name


def _public_username(entity: object) -> str | None:
    username = getattr(entity, "username", None)
    if isinstance(username, str) and username.strip():
        return username.strip()
    for item in getattr(entity, "usernames", None) or []:
        name = getattr(item, "username", None)
        if getattr(item, "active", True) and isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _channel_kind(entity: object) -> str:
    if getattr(entity, "megagroup", False):
        return "group"
    return "channel"


async def _disconnect(client: Any) -> None:
    disconnect = getattr(client, "disconnect", None)
    if disconnect is None:
        return
    try:
        await disconnect()
    except (OSError, RPCError, RuntimeError):
        return
