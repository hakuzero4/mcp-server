from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from tgchannel.summarize import TEXT_LIMIT, summarize_channel, summarize_message


class MessageActionPinMessage:
    pass


def message(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": 7,
        "message": "hello",
        "date": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "edit_date": None,
        "views": 10,
        "forwards": 2,
        "replies": SimpleNamespace(replies=4),
        "pinned": False,
        "photo": None,
        "sticker": None,
        "gif": None,
        "video": None,
        "voice": None,
        "audio": None,
        "document": None,
        "poll": None,
        "web_preview": None,
        "file": None,
        "grouped_id": None,
        "post_author": None,
        "action": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_channel_profile_and_about_limit() -> None:
    payload = summarize_channel(
        channel_id=5,
        title="Telegram",
        username="telegram",
        kind="channel",
        about="a" * 2005,
        participants=12,
    )
    assert payload["link"] == "https://t.me/telegram"
    assert payload["participants"] == 12
    assert payload["about_truncated"] is True
    assert len(payload["about"]) == 2000


def test_message_fields_and_video_name() -> None:
    payload = summarize_message(
        message(
            video=object(),
            file=SimpleNamespace(name="clip.mp4"),
            grouped_id=99,
            post_author="Editor",
            pinned=True,
        ),
        username="telegram",
    )
    assert payload["id"] == 7
    assert payload["date"] == "2026-01-02T03:04:05+00:00"
    assert payload["text"] == "hello"
    assert payload["truncated"] is False
    assert payload["views"] == 10
    assert payload["replies"] == 4
    assert payload["media"] == "video"
    assert payload["file_name"] == "clip.mp4"
    assert payload["grouped_id"] == 99
    assert payload["author"] == "Editor"
    assert payload["pinned"] is True
    assert payload["link"] == "https://t.me/telegram/7"


def test_photo_has_no_file_name_and_long_text_is_cut() -> None:
    payload = summarize_message(
        message(message="x" * (TEXT_LIMIT + 5), photo=object(), file=SimpleNamespace(name="a.jpg")),
        username="telegram",
    )
    assert payload["media"] == "photo"
    assert payload["file_name"] is None
    assert payload["truncated"] is True
    assert len(payload["text"]) == TEXT_LIMIT


def test_service_action_is_named() -> None:
    payload = summarize_message(message(message=None, action=MessageActionPinMessage()), username="telegram")
    assert payload["text"] == ""
    assert payload["action"] == "MessageActionPinMessage"
    assert payload["media"] is None
