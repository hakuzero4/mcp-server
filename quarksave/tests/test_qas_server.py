from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from quarksave.constants import NAMESPACE
from quarksave.exceptions import QasApiError
from quarksave.server import create_server


def tool_payload(result) -> object:
    if result.data is not None:
        return result.data
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    return json.loads(result.content[0].text)


async def test_tools_use_quarksave_namespace(server) -> None:
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert names == {
        f"{NAMESPACE}_list_tasks",
        f"{NAMESPACE}_get_task",
        f"{NAMESPACE}_get_share",
        f"{NAMESPACE}_list_save_path",
        f"{NAMESPACE}_search_shares",
        f"{NAMESPACE}_save",
        f"{NAMESPACE}_run_task",
        f"{NAMESPACE}_update_task",
        f"{NAMESPACE}_delete_task",
    }


async def test_resource_and_prompt_are_namespaced(server) -> None:
    async with Client(server) as client:
        resources = await client.list_resources()
        prompts = await client.list_prompts()
    assert "qas://quarksave/tasks" in {str(resource.uri) for resource in resources}
    assert f"{NAMESPACE}_save_share_guide" in {prompt.name for prompt in prompts}


async def test_unnamespaced_server_keeps_original_tool_names(qas_client: AsyncMock) -> None:
    server = create_server(namespaced=False, client=qas_client)
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert "save" in names
    assert f"{NAMESPACE}_save" not in names


async def test_save_link_only_uses_share_title(server, qas_client: AsyncMock) -> None:
    qas_client.share_detail.return_value = {"share": {"title": "电影/名"}}

    async with Client(server) as client:
        result = await client.call_tool(
            f"{NAMESPACE}_save",
            {"shareurl": "https://pan.quark.cn/s/abc"},
        )
    payload = tool_payload(result)
    assert payload["taskname"] == "电影 名"
    assert payload["savepath"] == "/电影 名"
    assert payload["subscribed"] is False
    qas_client.share_detail.assert_awaited()
    qas_client.add_task.assert_not_awaited()
    sent = qas_client.run_tasks.await_args.args[0][0]
    assert sent["savepath"] == "/电影 名"
    assert sent["pattern"] == ".*"


async def test_save_once_does_not_store_the_task(server, qas_client: AsyncMock) -> None:
    async with Client(server) as client:
        result = await client.call_tool(
            f"{NAMESPACE}_save",
            {
                "taskname": "名称",
                "shareurl": "https://pan.quark.cn/s/abc",
                "savepath": "/video/tv/名称",
            },
        )
    payload = tool_payload(result)
    assert payload["subscribed"] is False
    assert payload["log"] == "转存文件: a.mp4"
    qas_client.add_task.assert_not_awaited()
    qas_client.tasklist.assert_not_awaited()
    qas_client.share_detail.assert_not_awaited()
    sent = qas_client.run_tasks.await_args.args[0][0]
    assert sent["shareurl"] == "https://pan.quark.cn/s/abc"
    assert sent["savepath"] == "/video/tv/名称"
    assert sent["pattern"] == ".*"


async def test_save_subscribe_adds_then_runs(server, qas_client: AsyncMock) -> None:
    qas_client.tasklist.return_value = []
    qas_client.add_task.side_effect = lambda task: {**task, "addition": {"auto_unarchive": {"enable": False}}}

    async with Client(server) as client:
        result = await client.call_tool(
            f"{NAMESPACE}_save",
            {
                "taskname": "名称",
                "shareurl": "https://pan.quark.cn/s/abc",
                "savepath": "/video/tv/名称",
                "subscribe": True,
                "pattern": "$TV_MAGIC",
            },
        )
    payload = tool_payload(result)
    assert payload["subscribed"] is True
    assert payload["pattern"] == "$TV_MAGIC"
    assert "addition" not in payload
    stored = qas_client.add_task.await_args.args[0]
    assert stored["pattern"] == "$TV_MAGIC"
    assert qas_client.run_tasks.await_args.args[0][0]["addition"]["auto_unarchive"]["enable"] is False


async def test_save_subscribe_rejects_duplicate_name(server, qas_client: AsyncMock) -> None:
    qas_client.tasklist.return_value = [
        {"taskname": "名称", "shareurl": "https://pan.quark.cn/s/old", "savepath": "/video"}
    ]

    async with Client(server) as client:
        with pytest.raises(ToolError, match="already exists"):
            await client.call_tool(
                f"{NAMESPACE}_save",
                {
                    "taskname": "名称",
                    "shareurl": "https://pan.quark.cn/s/abc",
                    "savepath": "/video/tv/名称",
                    "subscribe": True,
                },
            )
    qas_client.add_task.assert_not_awaited()
    qas_client.run_tasks.assert_not_awaited()


async def test_saved_task_reports_run_failure(server, qas_client: AsyncMock) -> None:
    qas_client.tasklist.return_value = []
    qas_client.run_tasks.side_effect = QasApiError(0, "HTTP request failed: timeout")

    async with Client(server) as client:
        with pytest.raises(ToolError, match="was saved"):
            await client.call_tool(
                f"{NAMESPACE}_save",
                {
                    "taskname": "名称",
                    "shareurl": "https://pan.quark.cn/s/abc",
                    "savepath": "/video",
                    "subscribe": True,
                },
            )


async def test_get_share_summarizes(server, qas_client: AsyncMock) -> None:
    qas_client.share_detail.return_value = {
        "stoken": "secret",
        "share": {"title": "剧集"},
        "list": [{"file_name": "01.mp4", "fid": "fid-1", "dir": False, "size": 3, "obj_category": "video"}],
    }

    async with Client(server) as client:
        result = await client.call_tool(
            f"{NAMESPACE}_get_share",
            {"shareurl": "https://pan.quark.cn/s/abc"},
        )
    payload = tool_payload(result)
    assert payload["title"] == "剧集"
    assert payload["files"][0]["fid"] == "fid-1"
    assert "stoken" not in payload
    assert "secret" not in str(payload)


async def test_update_and_delete_replace_tasklist(server, qas_client: AsyncMock) -> None:
    qas_client.tasklist.return_value = [
        {
            "taskname": "名称",
            "shareurl": "https://pan.quark.cn/s/old",
            "savepath": "/video",
            "shareurl_ban": "失效",
            "pattern": ".*",
        },
        {"taskname": "其他", "shareurl": "https://pan.quark.cn/s/other", "savepath": "/movie"},
    ]

    async with Client(server) as client:
        updated = await client.call_tool(
            f"{NAMESPACE}_update_task",
            {"taskname": "名称", "shareurl": "https://pan.quark.cn/s/new"},
        )
        deleted = await client.call_tool(f"{NAMESPACE}_delete_task", {"taskname": "其他"})

    assert tool_payload(updated)["shareurl"] == "https://pan.quark.cn/s/new"
    assert "shareurl_ban" not in tool_payload(updated)
    replaced = qas_client.replace_tasklist.await_args_list[0].args[0]
    assert replaced[0]["shareurl"] == "https://pan.quark.cn/s/new"
    assert "shareurl_ban" not in replaced[0]
    assert replaced[1]["taskname"] == "其他"
    assert tool_payload(deleted) == {"deleted": "其他"}
    assert [item["taskname"] for item in qas_client.replace_tasklist.await_args_list[1].args[0]] == ["名称"]
