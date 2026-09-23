from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tgchannel.constants import NAMESPACE
from tgchannel.exceptions import TgApiError
from tgchannel.server import create_server


def tool_payload(result: object) -> object:
    data = getattr(result, "data", None)
    if data is not None:
        return data
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    content = getattr(result, "content", None)
    return json.loads(content[0].text)


async def test_tools_use_tgchannel_namespace(server) -> None:
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert names == {
        f"{NAMESPACE}_get_channel",
        f"{NAMESPACE}_list_messages",
        f"{NAMESPACE}_search_messages",
    }


async def test_unnamespaced_server_keeps_original_tool_names(tg_client: AsyncMock) -> None:
    bare = create_server(namespaced=False, client=tg_client)
    async with Client(bare) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert "list_messages" in names
    assert f"{NAMESPACE}_list_messages" not in names


async def test_list_messages_accepts_only_the_link(server, tg_client: AsyncMock) -> None:
    async with Client(server) as client:
        result = await client.call_tool(
            f"{NAMESPACE}_list_messages",
            {"channel": "https://t.me/s/telegram"},
        )
    payload = tool_payload(result)
    assert payload["username"] == "telegram"
    tg_client.list_messages.assert_awaited_once_with("telegram", limit=20, offset_id=0)


async def test_get_channel_parses_at_username(server, tg_client: AsyncMock) -> None:
    async with Client(server) as client:
        await client.call_tool(f"{NAMESPACE}_get_channel", {"channel": "@telegram"})
    tg_client.get_channel.assert_awaited_once_with("telegram")


async def test_search_forwards_query(server, tg_client: AsyncMock) -> None:
    async with Client(server) as client:
        await client.call_tool(
            f"{NAMESPACE}_search_messages",
            {"channel": "telegram", "query": " hello ", "limit": 5, "offset_id": 4},
        )
    tg_client.search_messages.assert_awaited_once_with(
        "telegram",
        query="hello",
        limit=5,
        offset_id=4,
    )


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_channel", {"channel": "https://t.me/+secret"}),
        ("list_messages", {"channel": "https://t.me/c/1/2"}),
        ("list_messages", {"channel": "@telegram", "limit": 101}),
        ("search_messages", {"channel": "@telegram", "query": "   "}),
        ("list_messages", {"channel": "@telegram", "offset_id": -1}),
    ],
)
async def test_invalid_arguments_do_not_call_telegram(server, tg_client: AsyncMock, tool: str, arguments: dict) -> None:
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool(f"{NAMESPACE}_{tool}", arguments)
    tg_client.get_channel.assert_not_awaited()
    tg_client.list_messages.assert_not_awaited()
    tg_client.search_messages.assert_not_awaited()


async def test_api_error_becomes_tool_error(server, tg_client: AsyncMock) -> None:
    tg_client.list_messages.side_effect = TgApiError("Telegram rate limit. Retry after 30 seconds.")
    async with Client(server) as client:
        with pytest.raises(ToolError, match="30"):
            await client.call_tool(f"{NAMESPACE}_list_messages", {"channel": "@telegram"})
