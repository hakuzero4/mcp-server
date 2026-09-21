from __future__ import annotations

import json
from unittest.mock import AsyncMock

from fastmcp import Client

from nginxproxy.constants import NAMESPACE
from nginxproxy.server import create_server


def tool_payload(result) -> object:
    if result.data is not None:
        return result.data
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    return json.loads(result.content[0].text)


async def test_tools_use_nginxproxy_namespace(server) -> None:
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert names
    assert all(name.startswith(f"{NAMESPACE}_") for name in names)
    assert f"{NAMESPACE}_list_proxy_hosts" in names
    assert f"{NAMESPACE}_create_proxy_host" in names
    assert f"{NAMESPACE}_create_service" in names
    assert f"{NAMESPACE}_create_letsencrypt_certificate" in names
    assert f"{NAMESPACE}_get_status" in names
    assert "list_proxy_hosts" not in names


async def test_resources_use_nginxproxy_namespace(server) -> None:
    async with Client(server) as client:
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
    uris = {str(resource.uri) for resource in resources}
    template_uris = {str(template.uri_template) for template in templates}
    assert "npm://nginxproxy/status" in uris
    assert "npm://nginxproxy/proxy-hosts" in uris
    assert "npm://nginxproxy/proxy-hosts/{host_id}" in template_uris


async def test_unnamespaced_server_keeps_original_tool_names(npm_client: AsyncMock) -> None:
    server = create_server(namespaced=False, client=npm_client)
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert "list_proxy_hosts" in names
    assert f"{NAMESPACE}_list_proxy_hosts" not in names


async def test_list_proxy_hosts_calls_api(server, npm_client: AsyncMock) -> None:
    npm_client.get.return_value = [{"id": 1, "domain_names": ["app.example.com"]}]
    async with Client(server) as client:
        result = await client.call_tool(
            f"{NAMESPACE}_list_proxy_hosts",
            {"query": "app.example.com", "expand": ["certificate"]},
        )
    assert tool_payload(result) == [{"id": 1, "domain_names": ["app.example.com"]}]
    npm_client.get.assert_awaited()
    args, kwargs = npm_client.get.await_args
    assert args[0] == "/nginx/proxy-hosts"
    assert kwargs["params"]["query"] == "app.example.com"
    assert kwargs["params"]["expand"] == "certificate"


async def test_create_proxy_host_payload(server, npm_client: AsyncMock) -> None:
    npm_client.post.return_value = {"id": 9, "domain_names": ["app.example.com"]}
    async with Client(server) as client:
        result = await client.call_tool(
            f"{NAMESPACE}_create_proxy_host",
            {
                "domain_names": ["app.example.com"],
                "forward_host": "127.0.0.1",
                "forward_port": 3000,
                "certificate_id": "new",
                "ssl_forced": True,
                "letsencrypt_email": "admin@example.com",
            },
        )
    assert tool_payload(result)["id"] == 9
    payload = npm_client.post.await_args.kwargs["json"]
    assert payload["domain_names"] == ["app.example.com"]
    assert payload["forward_port"] == 3000
    assert payload["certificate_id"] == "new"
    assert payload["meta"]["letsencrypt_agree"] is True
    assert payload["meta"]["letsencrypt_email"] == "admin@example.com"


async def test_create_service_attaches_custom_certificate(server, npm_client: AsyncMock) -> None:
    async def fake_get(path, params=None):
        if path == "/nginx/certificates":
            return [
                {
                    "id": 2,
                    "provider": "other",
                    "nice_name": "home.com",
                    "domain_names": ["*.home.com"],
                    "expires_on": "2035-11-18 07:11:06",
                }
            ]
        if path == "/nginx/proxy-hosts":
            return []
        raise AssertionError(path)

    npm_client.get.side_effect = fake_get
    npm_client.post.return_value = {
        "id": 24,
        "domain_names": ["app.home.com"],
        "forward_host": "10.0.0.10",
        "forward_port": 8080,
        "certificate_id": 2,
        "ssl_forced": True,
    }
    async with Client(server) as client:
        result = await client.call_tool(
            f"{NAMESPACE}_create_service",
            {
                "domain": "app.home.com",
                "ip": "10.0.0.10",
                "port": 8080,
                "use_custom_certificate": True,
            },
        )
    payload = tool_payload(result)
    assert payload["id"] == 24
    assert payload["certificate"]["id"] == 2
    assert payload["ssl_forced"] is True
    created = npm_client.post.await_args.kwargs["json"]
    assert created["domain_names"] == ["app.home.com"]
    assert created["forward_host"] == "10.0.0.10"
    assert created["forward_port"] == 8080
    assert created["certificate_id"] == 2
    assert created["ssl_forced"] is True


async def test_prompt_is_namespaced(server) -> None:
    async with Client(server) as client:
        prompts = await client.list_prompts()
    names = {prompt.name for prompt in prompts}
    assert f"{NAMESPACE}_create_https_proxy_guide" in names
