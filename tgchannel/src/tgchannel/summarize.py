"""Turn Telegram entities and messages into plain tool payloads."""

from __future__ import annotations

from typing import Any

TEXT_LIMIT = 4_000
ABOUT_LIMIT = 2_000
_MEDIA_KINDS = ("photo", "sticker", "gif", "video", "voice", "audio", "document")


def summarize_channel(
    *,
    channel_id: int,
    title: str,
    username: str,
    kind: str,
    about: str | None,
    participants: int | None,
) -> dict[str, Any]:
    """Profile fields for one public channel or public group."""
    text = about or ""
    truncated = len(text) > ABOUT_LIMIT
    if truncated:
        text = text[:ABOUT_LIMIT]
    count = participants if isinstance(participants, int) and not isinstance(participants, bool) else None
    return {
        "id": channel_id,
        "title": title or "",
        "username": username,
        "kind": kind,
        "about": text,
        "about_truncated": truncated,
        "participants": count,
        "link": f"https://t.me/{username}",
    }


def summarize_message(message: Any, *, username: str) -> dict[str, Any]:
    """One public post. Media is described, not downloaded."""
    raw = getattr(message, "message", None)
    if raw is None:
        raw = getattr(message, "text", None)
    text = raw if isinstance(raw, str) else ""
    truncated = len(text) > TEXT_LIMIT
    if truncated:
        text = text[:TEXT_LIMIT]
    media, file_name = _media(message)
    replies = getattr(message, "replies", None)
    reply_count = getattr(replies, "replies", None) if replies is not None else None
    if isinstance(reply_count, bool) or not isinstance(reply_count, int):
        reply_count = None
    action = getattr(message, "action", None)
    author = getattr(message, "post_author", None)
    if not isinstance(author, str) or not author.strip():
        author = None
    return {
        "id": getattr(message, "id", None),
        "date": _iso(getattr(message, "date", None)),
        "edited": _iso(getattr(message, "edit_date", None)),
        "text": text,
        "truncated": truncated,
        "views": _count(getattr(message, "views", None)),
        "forwards": _count(getattr(message, "forwards", None)),
        "replies": reply_count,
        "pinned": bool(getattr(message, "pinned", False)),
        "media": media,
        "file_name": file_name,
        "grouped_id": _count(getattr(message, "grouped_id", None)),
        "author": author,
        "action": type(action).__name__ if action is not None else None,
        "link": f"https://t.me/{username}/{getattr(message, 'id', '')}",
    }


def _media(message: Any) -> tuple[str | None, str | None]:
    file = getattr(message, "file", None)
    name = getattr(file, "name", None) if file is not None else None
    if not isinstance(name, str) or not name:
        name = None
    for kind in _MEDIA_KINDS:
        if getattr(message, kind, None):
            if kind == "photo":
                return kind, None
            return kind, name
    if getattr(message, "poll", None):
        return "poll", None
    if getattr(message, "web_preview", None):
        return "webpage", None
    return None, None


def _iso(value: Any) -> str | None:
    isoformat = getattr(value, "isoformat", None)
    if not callable(isoformat):
        return None
    return isoformat()


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
