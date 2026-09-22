from __future__ import annotations

import httpx
import pytest
import respx

from quarksave.client import QasClient
from quarksave.exceptions import QasApiError
from quarksave.settings import Settings

BASE = "http://127.0.0.1:5005"


@pytest.fixture
def settings() -> Settings:
    return Settings(url=f"{BASE}/", token="secret-token", _env_file=None)


@respx.mock
async def test_public_state_strips_secrets(settings: Settings) -> None:
    respx.get(f"{BASE}/data").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "cookie": ["secret-cookie"],
                    "api_token": "secret-token",
                    "push_config": {"QYWX": "notify-secret"},
                    "crontab": "0 8 * * *",
                    "magic_regex": {"$TV_MAGIC": {"pattern": ".*", "replace": "{E}"}},
                    "tasklist": [
                        {
                            "taskname": "名称",
                            "shareurl": "https://pan.quark.cn/s/abc",
                            "savepath": "/video/tv/名称",
                            "shareurl_ban": "失效",
                        }
                    ],
                },
            },
        )
    )

    client = QasClient(settings)
    try:
        state = await client.public_state()
    finally:
        await client.aclose()

    assert respx.calls.last.request.url.params["token"] == "secret-token"
    assert state["crontab"] == "0 8 * * *"
    assert state["tasks"][0]["shareurl_ban"] == "失效"
    dumped = str(state)
    assert "secret-cookie" not in dumped
    assert "notify-secret" not in dumped
    assert "api_token" not in state


@respx.mock
async def test_add_task_keeps_token_out_of_body(settings: Settings) -> None:
    route = respx.post(f"{BASE}/api/add_task").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "code": 0, "message": "任务添加成功", "data": {"taskname": "名称"}},
        )
    )

    client = QasClient(settings)
    try:
        saved = await client.add_task(
            {
                "taskname": "名称",
                "shareurl": "https://pan.quark.cn/s/abc",
                "savepath": "/video",
            }
        )
    finally:
        await client.aclose()

    assert saved["taskname"] == "名称"
    assert route.calls.last.request.url.params["token"] == "secret-token"
    assert b"secret-token" not in route.calls.last.request.content


@respx.mock
async def test_share_error_uses_data_error(settings: Settings) -> None:
    respx.post(f"{BASE}/get_share_detail").mock(
        return_value=httpx.Response(200, json={"success": False, "data": {"error": "分享已失效"}})
    )

    client = QasClient(settings)
    try:
        with pytest.raises(QasApiError, match="分享已失效") as exc_info:
            await client.share_detail("https://pan.quark.cn/s/abc")
    finally:
        await client.aclose()

    assert exc_info.value.status_code == 200


@respx.mock
async def test_run_tasks_reads_sse(settings: Settings) -> None:
    respx.post(f"{BASE}/run_script_now").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream;charset=utf-8"},
            text="data: 转存文件: a.mp4\n\ndata: [DONE]\n\n",
        )
    )

    client = QasClient(settings)
    try:
        log = await client.run_tasks([{"taskname": "名称"}])
    finally:
        await client.aclose()

    assert log == "转存文件: a.mp4"


@respx.mock
async def test_html_login_page_is_an_error(settings: Settings) -> None:
    respx.get(f"{BASE}/data").mock(
        return_value=httpx.Response(200, headers={"content-type": "text/html"}, text="<html>login</html>")
    )

    client = QasClient(settings)
    try:
        with pytest.raises(QasApiError, match="returned HTML"):
            await client.tasklist()
    finally:
        await client.aclose()


async def test_missing_token() -> None:
    client = QasClient(Settings(url=BASE, token="", _env_file=None))
    try:
        with pytest.raises(QasApiError, match="QAS_TOKEN"):
            await client.tasklist()
    finally:
        await client.aclose()


@respx.mock
async def test_transport_error_redacts_token(settings: Settings) -> None:
    respx.get(f"{BASE}/data").mock(side_effect=httpx.ConnectError(f"boom token={settings.token}"))

    client = QasClient(settings)
    try:
        with pytest.raises(QasApiError, match="HTTP request failed") as exc_info:
            await client.tasklist()
    finally:
        await client.aclose()

    assert settings.token not in str(exc_info.value)


def test_settings_read_qas_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QAS_URL", raising=False)
    monkeypatch.delenv("QAS_BASE_URL", raising=False)
    monkeypatch.delenv("QAS_TOKEN", raising=False)
    monkeypatch.setenv("QAS_BASE_URL", "http://192.0.2.15:5005/")
    monkeypatch.setenv("QAS_TOKEN", "abc")
    settings = Settings(_env_file=None)
    assert settings.url == "http://192.0.2.15:5005"
    assert settings.token == "abc"

    monkeypatch.delenv("QAS_BASE_URL")
    monkeypatch.setenv("QAS_URL", "http://192.0.2.16:5005/")
    settings = Settings(_env_file=None)
    assert settings.url == "http://192.0.2.16:5005"
