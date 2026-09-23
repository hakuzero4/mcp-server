from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run import ALL, build_app, discover_servers, parse_selection


def test_discover_includes_workspace_servers() -> None:
    servers = discover_servers()
    assert servers["nginxproxy"] == "nginxproxy.server"
    assert servers["quarksave"] == "quarksave.server"
    assert servers["tgchannel"] == "tgchannel.server"


def test_parse_all_and_subset() -> None:
    servers = {"nginxproxy": "nginxproxy.server", "other": "other.server"}
    assert parse_selection("all", servers) == ["nginxproxy", "other"]
    assert parse_selection("nginxproxy", servers) == ["nginxproxy"]
    assert parse_selection("nginxproxy,other", servers) == ["nginxproxy", "other"]


async def test_gateway_all_keeps_namespace() -> None:
    servers = discover_servers()
    mcp, names = build_app(ALL, servers)
    assert names == ["nginxproxy", "quarksave", "tgchannel"]
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert any(tool.name == "nginxproxy_create_service" for tool in tools)
    assert any(tool.name == "nginxproxy_list_proxy_hosts" for tool in tools)
    assert any(tool.name == "quarksave_save" for tool in tools)
    assert any(tool.name == "tgchannel_list_messages" for tool in tools)


async def test_single_server_matches_namespaced_tools() -> None:
    from nginxproxy.server import create_server

    mcp = create_server(namespaced=True, client=AsyncMock())
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert any(tool.name.startswith("nginxproxy_") for tool in tools)
