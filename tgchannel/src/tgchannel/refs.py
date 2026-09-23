"""Parse public Telegram channel references and tool limits."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from tgchannel.exceptions import RefError

_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
_HOSTS = {"t.me", "telegram.me"}
_PREVIEW = "s"
# Path roots that are not a public @username. `s` is the web preview prefix and is handled first.
_BLOCKED_ROOTS = {
    "joinchat",
    "c",
    "share",
    "addstickers",
    "addemoji",
    "addtheme",
    "proxy",
    "socks",
    "iv",
}
_PRIVATE = (
    "Only public channels with a username are supported. Private invite links are refused."
)
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_QUERY = 200


def parse_channel_ref(raw: str) -> str:
    """Return the public username from @name, t.me, t.me/s, or tg://resolve."""
    text = raw.strip()
    if not text:
        raise RefError("Channel reference is empty.")
    if text.startswith("@"):
        return _username(text[1:])
    if text.lower().startswith("tg:"):
        return _from_tg(text)
    if "://" not in text and re.match(r"^(?:www\.)?(?:t|telegram)\.me/", text, re.I):
        text = "https://" + text
    if "://" in text:
        return _from_url(text)
    return _username(text)


def require_limit(limit: int, *, upper: int = MAX_LIMIT) -> int:
    """Reject limits outside 1..upper. Booleans are not counts."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > upper:
        raise RefError(f"limit must be an integer from 1 to {upper}.")
    return limit


def require_offset(offset_id: int) -> int:
    """Reject negative message offsets. Zero means start from the newest post."""
    if isinstance(offset_id, bool) or not isinstance(offset_id, int) or offset_id < 0:
        raise RefError("offset_id must be an integer greater than or equal to 0.")
    return offset_id


def require_query(query: str) -> str:
    """Strip a channel search query and reject an empty or very long one."""
    if not isinstance(query, str):
        raise RefError("query is required.")
    cleaned = query.strip()
    if not cleaned:
        raise RefError("query is required.")
    if len(cleaned) > MAX_QUERY:
        raise RefError("query is too long.")
    return cleaned


def _username(value: str) -> str:
    name = value.strip().lstrip("@")
    if not _USERNAME.fullmatch(name):
        raise RefError(
            "Username must be 5–32 characters, start with a letter, "
            "and contain only letters, digits, and underscores."
        )
    return name


def _from_url(text: str) -> str:
    parsed = urlparse(text)
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if host not in _HOSTS:
        raise RefError("Not a Telegram channel link.")
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise RefError("Telegram link has no username.")
    first = parts[0]
    if first.startswith("+") or first in _BLOCKED_ROOTS:
        raise RefError(_PRIVATE)
    if first == _PREVIEW:
        if len(parts) < 2:
            raise RefError("Telegram preview link has no username.")
        target = parts[1]
    else:
        target = first
    if target.startswith("+"):
        raise RefError(_PRIVATE)
    return _username(target)


def _from_tg(text: str) -> str:
    parsed = urlparse(text)
    if parsed.netloc.lower() != "resolve":
        raise RefError(_PRIVATE)
    domain = parse_qs(parsed.query).get("domain", [""])[0]
    if not domain:
        raise RefError("Telegram link has no username.")
    return _username(domain)
