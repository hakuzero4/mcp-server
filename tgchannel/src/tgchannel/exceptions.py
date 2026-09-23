"""Errors raised by the Telegram channel client and reference parser."""


class TgError(Exception):
    """Base error for tgchannel."""


class TgConfigError(TgError):
    """API id, api hash, or session is missing or not logged in."""


class TgApiError(TgError):
    """A Telegram API call failed."""


class RefError(TgError):
    """A channel reference or tool argument is invalid."""


class ArchiveError(TgError):
    """The local channel archive rejected the request or the database file."""
