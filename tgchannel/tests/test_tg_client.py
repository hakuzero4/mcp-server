from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telethon.errors import ChannelPrivateError, FloodWaitError

from tgchannel.client import TgClient
from tgchannel.exceptions import TgApiError, TgConfigError
from tgchannel.settings import Settings


class User:
    pass


class Chat:
    pass


class ChannelForbidden:
    pass


class Channel:
    def __init__(self, **fields: object) -> None:
        self.__dict__.update(fields)


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "api_id": 1,
        "api_hash": "hash-secret",
        "session": "session-secret",
        "timeout": 5,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def flood(seconds: int) -> FloodWaitError:
    error = FloodWaitError.__new__(FloodWaitError)
    Exception.__init__(error, f"A wait of {seconds} seconds is required")
    error.seconds = seconds
    return error


def private_error() -> ChannelPrivateError:
    error = ChannelPrivateError.__new__(ChannelPrivateError)
    Exception.__init__(error, "channel private")
    return error


def channel(**overrides: object) -> Channel:
    fields: dict[str, object] = {
        "id": 100,
        "title": "Telegram News",
        "username": "telegram",
        "broadcast": True,
        "megagroup": False,
        "usernames": None,
    }
    fields.update(overrides)
    return Channel(**fields)


def full(about: str = "News", participants: int = 12) -> SimpleNamespace:
    return SimpleNamespace(full_chat=SimpleNamespace(about=about, participants_count=participants))


def post(text: str, message_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=message_id,
        message=text,
        date=None,
        edit_date=None,
        views=1,
        forwards=None,
        replies=None,
        pinned=False,
        photo=None,
        sticker=None,
        gif=None,
        video=None,
        voice=None,
        audio=None,
        document=None,
        poll=None,
        web_preview=None,
        file=None,
        grouped_id=None,
        post_author=None,
        action=None,
    )


def fake_telegram(entity: object, messages: list[object] | None = None, profile: object | None = None) -> AsyncMock:
    telegram = AsyncMock()
    telegram.get_entity = AsyncMock(return_value=entity)
    telegram.return_value = profile if profile is not None else full()

    def iter_messages(*_args: object, **_kwargs: object):
        async def generate():
            for item in messages or []:
                yield item

        return generate()

    telegram.iter_messages = Mock(side_effect=iter_messages)
    return telegram


def test_settings_blank_api_id_does_not_break_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TG_API_ID", "TG_API_HASH", "TG_SESSION", "TG_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TG_API_ID", "")
    monkeypatch.setenv("TG_API_HASH", "  ")
    loaded = Settings(_env_file=None)
    assert loaded.api_id == 0
    assert loaded.api_hash == ""
    assert loaded.timeout == 30

    monkeypatch.setenv("TG_API_ID", "12345")
    monkeypatch.setenv("TG_API_HASH", "app-hash")
    monkeypatch.setenv("TG_SESSION", " session ")
    monkeypatch.setenv("TG_TIMEOUT", "15")
    loaded = Settings(_env_file=None)
    assert loaded.api_id == 12345
    assert loaded.api_hash == "app-hash"
    assert loaded.session == "session"
    assert loaded.timeout == 15


def test_redact_hides_session_and_hash() -> None:
    client = TgClient(settings(), telegram=object())
    text = client.redact("failed session-secret and hash-secret")
    assert "session-secret" not in text
    assert "hash-secret" not in text
    assert "[redacted]" in text


async def test_missing_config_does_not_open_telegram() -> None:
    client = TgClient(settings(api_id=0, api_hash="", session=""))
    with pytest.raises(TgConfigError, match="TG_API_ID"):
        await client.get_channel("telegram")


async def test_injected_client_is_not_disconnected() -> None:
    telegram = fake_telegram(channel(), profile=full())
    client = TgClient(settings(api_id=0, api_hash="", session=""), telegram=telegram)
    await client.aclose()
    telegram.disconnect.assert_not_awaited()


async def test_get_channel_reads_profile_without_joining() -> None:
    telegram = fake_telegram(channel(), profile=full("Hello", 40))
    client = TgClient(settings(), telegram=telegram)
    payload = await client.get_channel("https://t.me/s/telegram")
    assert payload["username"] == "telegram"
    assert payload["title"] == "Telegram News"
    assert payload["about"] == "Hello"
    assert payload["participants"] == 40
    assert payload["kind"] == "channel"
    assert payload["link"] == "https://t.me/telegram"
    telegram.get_entity.assert_awaited_once_with("telegram")


async def test_username_list_is_used_when_the_main_field_is_empty() -> None:
    entity = channel(username=None, usernames=[SimpleNamespace(username="telegram", active=True)])
    telegram = fake_telegram(entity, profile=full())
    client = TgClient(settings(), telegram=telegram)
    payload = await client.get_channel("@telegram")
    assert payload["username"] == "telegram"


async def test_megagroup_is_a_group() -> None:
    telegram = fake_telegram(channel(broadcast=False, megagroup=True), profile=full())
    client = TgClient(settings(), telegram=telegram)
    payload = await client.get_channel("telegram")
    assert payload["kind"] == "group"


@pytest.mark.parametrize(
    ("entity", "match"),
    [
        (User(), "user account"),
        (Chat(), "no public username"),
        (ChannelForbidden(), "does not join"),
        (channel(username=None, usernames=[]), "no public username"),
    ],
)
async def test_resolve_refuses_non_public_chats(entity: object, match: str) -> None:
    telegram = fake_telegram(entity)
    client = TgClient(settings(), telegram=telegram)
    with pytest.raises(TgApiError, match=match):
        await client.get_channel("telegram")
    telegram.assert_not_awaited()


async def test_flood_wait_is_reported_and_not_retried() -> None:
    telegram = fake_telegram(channel())
    telegram.get_entity = AsyncMock(side_effect=flood(17))
    client = TgClient(settings(), telegram=telegram)
    with pytest.raises(TgApiError, match="17"):
        await client.get_channel("telegram")


async def test_private_history_is_reported() -> None:
    telegram = fake_telegram(channel())
    telegram.get_entity = AsyncMock(side_effect=private_error())
    client = TgClient(settings(), telegram=telegram)
    with pytest.raises(TgApiError, match="does not join"):
        await client.list_messages("telegram", limit=5)


async def test_list_messages_stops_at_the_limit() -> None:
    telegram = fake_telegram(channel(), [post("one", 3), post("two", 2), post("three", 1)])
    client = TgClient(settings(), telegram=telegram)
    payload = await client.list_messages("https://t.me/telegram/3", limit=2)
    assert [item["text"] for item in payload["messages"]] == ["one", "two"]
    assert "offset_id" not in telegram.iter_messages.call_args.kwargs
    assert telegram.iter_messages.call_args.kwargs["limit"] == 2


async def test_get_messages_reports_ids_that_are_missing() -> None:
    telegram = fake_telegram(channel())
    telegram.get_messages = AsyncMock(return_value=[post("hello", 7), None])
    client = TgClient(settings(), telegram=telegram)
    payload = await client.get_messages("https://t.me/telegram", [7, 9])
    assert [item["id"] for item in payload["messages"]] == [7]
    assert payload["missing"] == ["telegram:9"]
    assert telegram.get_messages.await_args.kwargs["ids"] == [7, 9]


async def test_search_passes_query_and_offset() -> None:
    telegram = fake_telegram(channel(), [post("hello", 8)])
    client = TgClient(settings(), telegram=telegram)
    payload = await client.search_messages("telegram", query=" hello ", limit=5, offset_id=9)
    assert payload["messages"][0]["id"] == 8
    kwargs = telegram.iter_messages.call_args.kwargs
    assert kwargs["search"] == "hello"
    assert kwargs["limit"] == 5
    assert kwargs["offset_id"] == 9


async def test_value_error_username_is_not_found() -> None:
    telegram = fake_telegram(channel())
    telegram.get_entity = AsyncMock(side_effect=ValueError('No user has "missing" as username'))
    client = TgClient(settings(), telegram=telegram)
    with pytest.raises(TgApiError, match="No public chat named @telegram"):
        await client.get_channel("telegram")
