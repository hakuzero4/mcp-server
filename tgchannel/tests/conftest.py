from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tgchannel.server import create_server


@pytest.fixture
def tg_client() -> AsyncMock:
    client = AsyncMock()
    client.get_channel = AsyncMock(return_value={"username": "telegram", "title": "Telegram"})
    client.list_messages = AsyncMock(return_value={"username": "telegram", "messages": []})
    client.search_messages = AsyncMock(return_value={"username": "telegram", "messages": []})
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def server(tg_client: AsyncMock):
    return create_server(namespaced=True, client=tg_client)
