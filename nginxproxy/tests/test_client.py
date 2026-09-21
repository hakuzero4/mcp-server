from __future__ import annotations

import httpx
import pytest
import respx

from nginxproxy.client import NpmClient, normalize_api_url
from nginxproxy.exceptions import NpmApiError
from nginxproxy.settings import Settings

API = "http://127.0.0.1:81/api"


def test_normalize_api_url_appends_api() -> None:
    assert normalize_api_url("http://127.0.0.1:81") == API
    assert normalize_api_url("http://127.0.0.1:81/") == API
    assert normalize_api_url(f"{API}/") == API


@pytest.fixture
def settings() -> Settings:
    return Settings(url="http://127.0.0.1:81", email="admin@example.com", password="secret")


@respx.mock
async def test_login_and_authenticated_get(settings: Settings) -> None:
    respx.post(f"{API}/tokens").mock(
        return_value=httpx.Response(200, json={"token": "jwt-1", "expires": "2099-01-01T00:00:00Z"})
    )
    respx.get(f"{API}/nginx/proxy-hosts").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "domain_names": ["app.example.com"]}])
    )

    client = NpmClient(settings)
    try:
        hosts = await client.get("/nginx/proxy-hosts")
    finally:
        await client.aclose()

    assert hosts[0]["id"] == 1
    login_call = respx.calls[0]
    assert login_call.request.url.path == "/api/tokens"
    assert b"admin@example.com" in login_call.request.content
    auth_call = respx.calls[1]
    assert auth_call.request.headers["Authorization"] == "Bearer jwt-1"


@respx.mock
async def test_401_relogs_in_and_retries(settings: Settings) -> None:
    respx.post(f"{API}/tokens").mock(
        side_effect=[
            httpx.Response(200, json={"token": "jwt-old"}),
            httpx.Response(200, json={"token": "jwt-new"}),
        ]
    )
    route = respx.get(f"{API}/nginx/proxy-hosts").mock(
        side_effect=[
            httpx.Response(401, json={"error": {"code": 401, "message": "Unauthorized"}}),
            httpx.Response(200, json=[{"id": 2}]),
        ]
    )

    client = NpmClient(settings)
    try:
        hosts = await client.get("/nginx/proxy-hosts")
    finally:
        await client.aclose()

    assert hosts == [{"id": 2}]
    assert route.call_count == 2
    assert respx.calls.last.request.headers["Authorization"] == "Bearer jwt-new"


@respx.mock
async def test_api_error_includes_message(settings: Settings) -> None:
    respx.post(f"{API}/tokens").mock(return_value=httpx.Response(200, json={"token": "jwt"}))
    respx.post(f"{API}/nginx/proxy-hosts").mock(
        return_value=httpx.Response(400, json={"error": {"code": 400, "message": "Domains are invalid"}})
    )

    client = NpmClient(settings)
    try:
        with pytest.raises(NpmApiError, match="Domains are invalid") as exc_info:
            await client.post("/nginx/proxy-hosts", json={"domain_names": []})
    finally:
        await client.aclose()

    assert exc_info.value.status_code == 400


@respx.mock
async def test_existing_token_skips_login() -> None:
    settings = Settings(url="http://127.0.0.1:81", token="preissued", email="", password="")
    respx.get(f"{API}/").mock(return_value=httpx.Response(200, json={"status": "OK"}))

    client = NpmClient(settings)
    try:
        status = await client.get("/")
    finally:
        await client.aclose()

    assert status["status"] == "OK"
    assert not any(call.request.url.path.endswith("/tokens") for call in respx.calls)
