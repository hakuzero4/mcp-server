"""One-time user login. Prints a session string and does not store the phone or 2FA password."""

from __future__ import annotations

import asyncio
import getpass
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession

from tgchannel.settings import Settings

_LOGIN_HINT = "uv run python -m tgchannel.login"


def require_interactive() -> None:
    """Refuse to prompt when stdin is not a terminal, so Docker cannot hang on input."""
    if not sys.stdin.isatty():
        raise SystemExit(
            "Login needs an interactive terminal. Run it on your computer, then set TG_SESSION."
        )


def require_api(settings: Settings) -> None:
    """The login flow needs the app id and hash. The phone is asked for separately."""
    if settings.api_id <= 0 or not settings.api_hash:
        raise SystemExit(f"Set TG_API_ID and TG_API_HASH in the environment or .env, then {_LOGIN_HINT}")


async def login(settings: Settings) -> str:
    """Ask Telegram for a login code and return a StringSession."""
    require_api(settings)
    client = TelegramClient(StringSession(), settings.api_id, settings.api_hash)
    try:
        await client.start(
            phone=lambda: input("手机号（国际格式，例如 +8613800000000）: ").strip(),
            code_callback=lambda: input("Telegram 验证码: ").strip(),
            password=lambda: getpass.getpass("两步验证密码: "),
        )
        if not await client.is_user_authorized():
            raise SystemExit("Login did not complete.")
        saved = client.session.save()
    finally:
        await client.disconnect()
    if not isinstance(saved, str) or not saved:
        raise SystemExit("Login did not produce a session.")
    return saved


def main() -> None:
    require_interactive()
    settings = Settings()
    require_api(settings)
    print(
        "用 Telegram 用户账号登录，不要填 Bot token。\n"
        "验证码会发到 Telegram。两步验证密码只在这次输入，不会写入 .env。",
        file=sys.stderr,
    )
    session = asyncio.run(login(settings))
    print("把下一行写入 .env 的 TG_SESSION。不要提交，也不要贴到聊天里。", file=sys.stderr)
    print(session)


if __name__ == "__main__":
    main()
