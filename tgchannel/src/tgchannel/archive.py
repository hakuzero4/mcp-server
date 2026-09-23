"""Local SQLite archive of public channel posts.

Identity is `(username, message id)`. Saving the same post again overwrites
that row. The file is opened on the first archive call, not at import.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tgchannel.exceptions import ArchiveError

TEXT_LIMIT = 4_000
PREVIEW_LIMIT = 200
_MAX_BATCH = 100
_MAX_MESSAGE_ID = 10**18
_MEDIA = {"photo", "sticker", "gif", "video", "voice", "audio", "document", "poll", "webpage"}
_CONTENT = (
    "date",
    "edited",
    "text",
    "truncated",
    "views",
    "forwards",
    "replies",
    "pinned",
    "media",
    "file_name",
    "grouped_id",
    "author",
    "action",
    "link",
)
_COLUMNS = (
    "username",
    "id",
    *_CONTENT,
    "saved_at",
    "updated_at",
)
_SCHEMA = """
CREATE TABLE messages (
  username TEXT NOT NULL,
  id INTEGER NOT NULL,
  date TEXT,
  edited TEXT,
  text TEXT NOT NULL DEFAULT '',
  truncated INTEGER NOT NULL DEFAULT 0,
  views INTEGER,
  forwards INTEGER,
  replies INTEGER,
  pinned INTEGER NOT NULL DEFAULT 0,
  media TEXT,
  file_name TEXT,
  grouped_id INTEGER,
  author TEXT,
  action TEXT,
  link TEXT NOT NULL,
  saved_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (username, id)
);
CREATE INDEX idx_messages_date ON messages (username, date);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Archive:
    """One SQLite file of saved channel posts."""

    def __init__(self, path: str, *, clock: Callable[[], str] | None = None, timeout: float = 5.0) -> None:
        self.path = path
        self.timeout = timeout
        self._clock = clock or _utc_now
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def ensure_configured(self) -> None:
        """Reject a missing path before any Telegram call or file is created."""
        if not isinstance(self.path, str) or not self.path.strip():
            raise ArchiveError("Set TG_STORE_PATH.")

    async def save(self, username: str, messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Insert or overwrite posts from one channel."""
        name = _username(username)
        prepared = _prepare_batch(name, messages)
        return await asyncio.to_thread(self._save, name, prepared)

    async def list_saved(self, username: str, *, limit: int, offset: int) -> dict[str, Any]:
        """Return saved posts, newest message date first. Text is a short preview."""
        name = _username(username)
        return await asyncio.to_thread(self._list, name, limit, offset)

    async def count_saved(self, username: str) -> dict[str, Any]:
        """Count saved posts for one channel."""
        name = _username(username)
        return await asyncio.to_thread(self._count, name)

    async def search_saved(self, username: str, query: str, *, limit: int) -> dict[str, Any]:
        """Find saved posts whose text contains the query."""
        name = _username(username)
        return await asyncio.to_thread(self._search, name, query, limit)

    async def get_saved(self, username: str, message_id: int) -> dict[str, Any]:
        """Return one saved post, including its full text."""
        name = _username(username)
        return await asyncio.to_thread(self._get, name, message_id)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _save(self, username: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        inserted = updated = unchanged = 0
        with self._lock:
            conn = self._connect()
            _begin(conn)
            try:
                for item in messages:
                    row = conn.execute(
                        "SELECT * FROM messages WHERE username = ? AND id = ?",
                        (item["username"], item["id"]),
                    ).fetchone()
                    if row is None:
                        stamp = self._clock()
                        conn.execute(
                            """
                            INSERT INTO messages (
                              username, id, date, edited, text, truncated, views, forwards, replies,
                              pinned, media, file_name, grouped_id, author, action, link,
                              saved_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item["username"],
                                item["id"],
                                item["date"],
                                item["edited"],
                                item["text"],
                                item["truncated"],
                                item["views"],
                                item["forwards"],
                                item["replies"],
                                item["pinned"],
                                item["media"],
                                item["file_name"],
                                item["grouped_id"],
                                item["author"],
                                item["action"],
                                item["link"],
                                stamp,
                                stamp,
                            ),
                        )
                        inserted += 1
                        continue
                    if all(row[name] == item[name] for name in _CONTENT):
                        unchanged += 1
                        continue
                    conn.execute(
                        """
                        UPDATE messages
                        SET date = ?, edited = ?, text = ?, truncated = ?, views = ?, forwards = ?,
                            replies = ?, pinned = ?, media = ?, file_name = ?, grouped_id = ?,
                            author = ?, action = ?, link = ?, updated_at = ?
                        WHERE username = ? AND id = ?
                        """,
                        (
                            item["date"],
                            item["edited"],
                            item["text"],
                            item["truncated"],
                            item["views"],
                            item["forwards"],
                            item["replies"],
                            item["pinned"],
                            item["media"],
                            item["file_name"],
                            item["grouped_id"],
                            item["author"],
                            item["action"],
                            item["link"],
                            self._clock(),
                            item["username"],
                            item["id"],
                        ),
                    )
                    updated += 1
                conn.execute("COMMIT")
            except Exception as exc:
                _rollback(conn)
                if isinstance(exc, ArchiveError):
                    raise
                raise ArchiveError("Write failed.") from exc
        return {
            "username": username,
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "keys": [f"{item['username']}:{item['id']}" for item in messages],
        }

    def _list(self, username: str, limit: int, offset: int) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE username = ?
                ORDER BY CASE WHEN date IS NULL THEN 1 ELSE 0 END, date DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (username, limit, offset),
            ).fetchall()
        return {"username": username, "messages": [_public(row, preview=True) for row in rows]}

    def _count(self, username: str) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE username = ?",
                (username,),
            ).fetchone()
        return {"username": username, "count": int(row["n"])}

    def _search(self, username: str, query: str, limit: int) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE username = ? AND text LIKE ? ESCAPE '\\'
                ORDER BY CASE WHEN date IS NULL THEN 1 ELSE 0 END, date DESC, id DESC
                LIMIT ?
                """,
                (username, _like(query), limit),
            ).fetchall()
        return {"username": username, "messages": [_public(row, preview=True) for row in rows]}

    def _get(self, username: str, message_id: int) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT * FROM messages WHERE username = ? AND id = ?",
                (username, message_id),
            ).fetchone()
        if row is None:
            raise ArchiveError(f"No saved message {username}:{message_id}.")
        return _public(row, preview=False)

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self.ensure_configured()
        target = Path(self.path)
        if target.exists() and target.is_dir():
            raise ArchiveError("TG_STORE_PATH is a directory.")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
        except OSError as exc:
            raise ArchiveError(f"Cannot open TG_STORE_PATH ({exc.strerror}).") from exc
        except sqlite3.Error as exc:
            raise ArchiveError("TG_STORE_PATH is not a channel archive.") from exc
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA trusted_schema=OFF")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(f"PRAGMA busy_timeout = {_busy_ms(self.timeout)}")
            self._ensure_schema(conn, target)
            conn.execute("PRAGMA journal_mode=WAL")
        except ArchiveError:
            conn.close()
            raise
        except sqlite3.Error as exc:
            conn.close()
            raise ArchiveError("TG_STORE_PATH is not a channel archive.") from exc
        except Exception:
            conn.close()
            raise
        self._conn = conn
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection, target: Path) -> None:
        try:
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        except sqlite3.Error as exc:
            raise ArchiveError("TG_STORE_PATH is not a channel archive.") from exc
        if not names and version == 0:
            conn.executescript(_SCHEMA)
            conn.execute("PRAGMA user_version = 1")
            _tighten(target)
            return
        columns = [row[1] for row in conn.execute("PRAGMA table_info(messages)")] if names == {"messages"} else []
        if names != {"messages"} or version != 1 or columns != list(_COLUMNS):
            raise ArchiveError("TG_STORE_PATH is not a channel archive.")


def _prepare_batch(username: str, messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    name = _username(username)
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        raise ArchiveError("messages must be a list.")
    if len(messages) > _MAX_BATCH:
        raise ArchiveError("A channel save accepts at most 100 messages.")
    collapsed: dict[int, dict[str, Any]] = {}
    order: list[int] = []
    for message in messages:
        item = _prepare_message(name, message)
        if item["id"] not in collapsed:
            order.append(item["id"])
        collapsed[item["id"]] = item
    return [collapsed[message_id] for message_id in order]


def _prepare_message(username: str, message: object) -> dict[str, Any]:
    if not isinstance(message, Mapping):
        raise ArchiveError("Each message must be an object.")
    message_id = _message_id(message.get("id"))
    if message_id is None:
        raise ArchiveError("Message has no id.")
    text = message.get("text")
    if not isinstance(text, str):
        text = ""
    return {
        "username": username,
        "id": message_id,
        "date": _time(message.get("date")),
        "edited": _time(message.get("edited")),
        "text": text[:TEXT_LIMIT],
        "truncated": _flag(message.get("truncated")) or int(len(text) > TEXT_LIMIT),
        "views": _count(message.get("views")),
        "forwards": _count(message.get("forwards")),
        "replies": _count(message.get("replies")),
        "pinned": _flag(message.get("pinned")),
        "media": _media(message.get("media")),
        "file_name": _short_text(message.get("file_name"), 200),
        "grouped_id": _count(message.get("grouped_id")),
        "author": _short_text(message.get("author"), 200),
        "action": _short_text(message.get("action"), 80),
        "link": f"https://t.me/{username}/{message_id}",
    }


def _public(row: sqlite3.Row, *, preview: bool) -> dict[str, Any]:
    text = row["text"] or ""
    if preview:
        text = text[:PREVIEW_LIMIT]
    return {
        "key": f"{row['username']}:{row['id']}",
        "username": row["username"],
        "id": row["id"],
        "date": row["date"],
        "edited": row["edited"],
        "text": text,
        "truncated": bool(row["truncated"]),
        "views": row["views"],
        "forwards": row["forwards"],
        "replies": row["replies"],
        "pinned": bool(row["pinned"]),
        "media": row["media"],
        "file_name": row["file_name"],
        "grouped_id": row["grouped_id"],
        "author": row["author"],
        "action": row["action"],
        "link": row["link"],
        "saved_at": row["saved_at"],
        "updated_at": row["updated_at"],
    }


def _username(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArchiveError("Channel username is required.")
    return value.strip().lower()


def _message_id(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.isdigit():
        number = int(value)
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    else:
        return None
    if number < 1 or number > _MAX_MESSAGE_ID:
        return None
    return number


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _flag(value: object) -> int:
    if value is True or value == 1:
        return 1
    return 0


def _media(value: object) -> str | None:
    if isinstance(value, str) and value in _MEDIA:
        return value
    return None


def _short_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:limit]


def _time(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    utc = parsed.astimezone(timezone.utc)
    if utc.microsecond:
        return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond:06d}Z"
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _like(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _busy_ms(timeout: float) -> int:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        return 5000
    milliseconds = int(timeout * 1000)
    if milliseconds < 1:
        return 1
    return milliseconds


def _begin(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.Error as exc:
        raise ArchiveError("Write failed.") from exc


def _rollback(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        return


def _tighten(path: Path) -> None:
    if os.name == "nt" or not path.is_file():
        return
    os.chmod(path, 0o600)
