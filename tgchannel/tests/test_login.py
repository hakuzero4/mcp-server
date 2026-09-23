from __future__ import annotations

import sys

import pytest

from tgchannel.login import require_api, require_interactive
from tgchannel.settings import Settings


def test_login_refuses_a_noninteractive_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit, match="interactive"):
        require_interactive()


def test_login_requires_api_credentials() -> None:
    with pytest.raises(SystemExit, match="TG_API_ID"):
        require_api(Settings(api_id=0, api_hash="", _env_file=None))
    require_api(Settings(api_id=1, api_hash="hash", _env_file=None))
