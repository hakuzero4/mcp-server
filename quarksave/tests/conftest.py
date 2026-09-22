from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quarksave.server import create_server


@pytest.fixture
def qas_client() -> AsyncMock:
    client = AsyncMock()
    client.public_state = AsyncMock(return_value={"crontab": "", "magic_regex": {}, "tasks": []})
    client.tasklist = AsyncMock(return_value=[])
    client.share_detail = AsyncMock(return_value={"list": []})
    client.savepath_detail = AsyncMock(return_value={"list": [], "paths": []})
    client.search = AsyncMock(return_value=[])
    client.add_task = AsyncMock(side_effect=lambda task: dict(task))
    client.replace_tasklist = AsyncMock(return_value=None)
    client.run_tasks = AsyncMock(return_value="转存文件: a.mp4")
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def server(qas_client: AsyncMock):
    return create_server(namespaced=True, client=qas_client)
