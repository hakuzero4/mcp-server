from __future__ import annotations

import pytest

from tgchannel.exceptions import RefError
from tgchannel.refs import parse_channel_ref, require_limit, require_offset, require_query


@pytest.mark.parametrize(
    ("raw", "username"),
    [
        ("telegram", "telegram"),
        ("abcde", "abcde"),
        ("a" + "b" * 31, "a" + "b" * 31),
        ("@telegram", "telegram"),
        ("  @telegram  ", "telegram"),
        ("https://t.me/telegram", "telegram"),
        ("https://t.me/telegram/", "telegram"),
        ("https://t.me/telegram/123", "telegram"),
        ("https://t.me/s/telegram", "telegram"),
        ("https://t.me/s/telegram/123", "telegram"),
        ("http://telegram.me/telegram", "telegram"),
        ("t.me/telegram", "telegram"),
        ("https://www.t.me/Telegram", "Telegram"),
        ("https://t.me/telegram?single", "telegram"),
        ("tg://resolve?domain=telegram", "telegram"),
    ],
)
def test_parse_public_username(raw: str, username: str) -> None:
    assert parse_channel_ref(raw) == username


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "@ab",
        "12345",
        "a" + "b" * 32,
        "https://example.com/telegram",
        "https://t.me/",
        "https://t.me/s/",
        "https://t.me/+abcdef",
        "https://t.me/joinchat/abcdef",
        "https://t.me/c/123/456",
        "https://t.me/share/url",
        "tg://join?invite=abcdef",
    ],
)
def test_parse_rejects_private_and_invalid(raw: str) -> None:
    with pytest.raises(RefError):
        parse_channel_ref(raw)


def test_limits() -> None:
    assert require_limit(20) == 20
    assert require_limit(100) == 100
    assert require_offset(0) == 0
    with pytest.raises(RefError):
        require_limit(0)
    with pytest.raises(RefError):
        require_limit(101)
    with pytest.raises(RefError):
        require_limit(True)  # type: ignore[arg-type]
    with pytest.raises(RefError):
        require_offset(-1)
    assert require_query("  hello ") == "hello"
    with pytest.raises(RefError):
        require_query("   ")
    with pytest.raises(RefError):
        require_query("x" * 201)
