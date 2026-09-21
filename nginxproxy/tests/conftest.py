from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from nginxproxy.server import create_server
from nginxproxy.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        url="http://127.0.0.1:81",
        email="admin@example.com",
        password="secret",
        token="",
    )


@pytest.fixture
def npm_client() -> AsyncMock:
    client = AsyncMock()
    client.get = AsyncMock(return_value={"status": "OK"})
    client.post = AsyncMock(return_value={"id": 1})
    client.put = AsyncMock(return_value={"id": 1})
    client.delete = AsyncMock(return_value=True)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def server(npm_client: AsyncMock):
    return create_server(namespaced=True, client=npm_client)
