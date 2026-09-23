from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tgchannel.archive import Archive
from tgchannel.exceptions import ArchiveError


def _post(message_id: int, text: str, **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "id": message_id,
        "date": "2026-09-23T08:00:00+08:00",
        "edited": None,
        "text": text,
        "truncated": False,
        "views": 3,
        "forwards": 1,
        "replies": 0,
        "pinned": False,
        "media": "photo",
        "file_name": None,
        "grouped_id": None,
        "author": "desk",
        "action": None,
    }
    body.update(extra)
    return body


async def test_same_post_stays_one_row_until_a_field_changes(tmp_path: Path) -> None:
    stamps = iter(["2020-01-01T00:00:00Z", "2021-01-01T00:00:00Z"])
    archive = Archive(str(tmp_path / "tg.sqlite"), clock=lambda: next(stamps))
    first = await archive.save("Telegram", [_post(7, "hello")])
    assert first["inserted"] == 1
    assert first["keys"] == ["telegram:7"]

    second = await archive.save("telegram", [_post(7, "hello", date="2026-09-23T00:00:00Z")])
    assert second["unchanged"] == 1
    stored = await archive.get_saved("telegram", 7)
    assert stored["updated_at"] == "2020-01-01T00:00:00Z"
    assert stored["saved_at"] == "2020-01-01T00:00:00Z"
    assert stored["date"] == "2026-09-23T00:00:00Z"

    changed = await archive.save("telegram", [_post(7, "hello", views=9)])
    assert changed["updated"] == 1
    assert (await archive.count_saved("telegram"))["count"] == 1
    assert (await archive.get_saved("telegram", 7))["views"] == 9
    assert (await archive.get_saved("telegram", 7))["updated_at"] == "2021-01-01T00:00:00Z"
    archive.close()


async def test_same_text_in_another_channel_is_another_row(tmp_path: Path) -> None:
    archive = Archive(str(tmp_path / "tg.sqlite"))
    result = await archive.save("telegram", [_post(7, "same")])
    assert result["inserted"] == 1
    other = await archive.save("durov", [_post(7, "same")])
    assert other["keys"] == ["durov:7"]
    assert (await archive.count_saved("telegram"))["count"] == 1
    assert (await archive.count_saved("durov"))["count"] == 1
    archive.close()


async def test_a_message_without_an_id_writes_nothing(tmp_path: Path) -> None:
    archive = Archive(str(tmp_path / "tg.sqlite"))
    await archive.save("telegram", [_post(7, "keep")])
    with pytest.raises(ArchiveError, match="no id"):
        await archive.save("telegram", [_post(8, "new"), {"text": "missing"}])
    assert (await archive.count_saved("telegram"))["count"] == 1
    archive.close()


async def test_search_is_literal_and_matches_chinese(tmp_path: Path) -> None:
    archive = Archive(str(tmp_path / "tg.sqlite"))
    await archive.save(
        "telegram",
        [
            _post(1, "进度 100% 完成"),
            _post(2, "今天发布了关键词公告"),
            _post(3, "axb"),
            _post(4, "a_b"),
        ],
    )
    percent = await archive.search_saved("telegram", "100%", limit=20)
    assert [item["key"] for item in percent["messages"]] == ["telegram:1"]
    chinese = await archive.search_saved("telegram", "关键词", limit=20)
    assert [item["key"] for item in chinese["messages"]] == ["telegram:2"]
    underscore = await archive.search_saved("telegram", "_", limit=20)
    assert [item["key"] for item in underscore["messages"]] == ["telegram:4"]
    archive.close()


async def test_list_previews_text_and_get_returns_the_stored_fields(tmp_path: Path) -> None:
    archive = Archive(str(tmp_path / "tg.sqlite"))
    text = "字" * 250
    await archive.save("telegram", [_post(7, text, media="video", file_name="clip.mp4")])
    listed = await archive.list_saved("telegram", limit=20, offset=0)
    assert listed["messages"][0]["text"] == "字" * 200
    assert listed["messages"][0]["media"] == "video"
    stored = await archive.get_saved("telegram", 7)
    assert stored["text"] == text
    assert stored["file_name"] == "clip.mp4"
    assert stored["author"] == "desk"
    assert set(stored) == {
        "key",
        "username",
        "id",
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
        "saved_at",
        "updated_at",
    }
    archive.close()


async def test_empty_path_does_not_create_a_file(tmp_path: Path) -> None:
    archive = Archive("")
    with pytest.raises(ArchiveError, match="TG_STORE_PATH"):
        await archive.count_saved("telegram")
    assert list(tmp_path.iterdir()) == []


async def test_a_foreign_database_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "other.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE notes (id INTEGER)")
    conn.execute("INSERT INTO notes (id) VALUES (1)")
    conn.commit()
    conn.close()
    archive = Archive(str(path))
    with pytest.raises(ArchiveError, match="not a channel archive"):
        await archive.count_saved("telegram")
    archive.close()
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT id FROM notes").fetchone()[0] == 1
    conn.close()
    assert not Path(str(path) + "-wal").exists()
