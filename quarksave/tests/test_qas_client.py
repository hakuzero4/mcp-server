from __future__ import annotations

import hashlib

import httpx
import pytest
import respx

from quarksave.client import QasClient, api_token
from quarksave.exceptions import QasApiError
from quarksave.settings import Settings

BASE = "http://127.0.0.1:5005"


def test_api_token_matches_webui_formula() -> None:
    digest = hashlib.md5(b"tokenadminsecret-pass+-*/").hexdigest()
    assert api_token("admin", "secret-pass") == digest[8:24]


@pytest.fixture
def settings() -> Settings:
    return Settings(url=f"{BASE}/", username="admin", password="secret-pass", _env_file=None)


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

    assert respx.calls.last.request.url.params["token"] == api_token("admin", "secret-pass")
    assert "secret-pass" not in str(respx.calls.last.request.url)
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
    assert route.calls.last.request.url.params["token"] == api_token("admin", "secret-pass")
    assert b"secret-pass" not in route.calls.last.request.content


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


async def test_missing_password() -> None:
    client = QasClient(Settings(url=BASE, username="admin", password="", _env_file=None))
    try:
        with pytest.raises(QasApiError, match="QAS_PASSWORD"):
            await client.tasklist()
    finally:
        await client.aclose()


@respx.mock
async def test_transport_error_redacts_password(settings: Settings) -> None:
    respx.get(f"{BASE}/data").mock(
        side_effect=httpx.ConnectError(f"boom password={settings.password} token={api_token('admin', 'secret-pass')}")
    )

    client = QasClient(settings)
    try:
        with pytest.raises(QasApiError, match="HTTP request failed") as exc_info:
            await client.tasklist()
    finally:
        await client.aclose()

    message = str(exc_info.value)
    assert settings.password not in message
    assert api_token("admin", "secret-pass") not in message


def test_settings_read_qas_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("QAS_URL", "QAS_BASE_URL", "QAS_USERNAME", "QAS_PASSWORD", "QAS_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("QAS_BASE_URL", "http://192.0.2.15:5005/")
    monkeypatch.setenv("QAS_USERNAME", "admin")
    monkeypatch.setenv("QAS_PASSWORD", "secret-pass")
    settings = Settings(_env_file=None)
    assert settings.url == "http://192.0.2.15:5005"
    assert settings.username == "admin"
    assert settings.password == "secret-pass"

    monkeypatch.delenv("QAS_BASE_URL")
    monkeypatch.setenv("QAS_URL", "http://192.0.2.16:5005/")
    settings = Settings(_env_file=None)
    assert settings.url == "http://192.0.2.16:5005"
