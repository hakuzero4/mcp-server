from __future__ import annotations

import pytest

from quarksave.exceptions import TaskError
from quarksave.tasks import (
    apply_update,
    build_task,
    name_from_share,
    parse_sse,
    require_savepath,
    summarize_share,
    summarize_task,
    trim_log,
)


def test_build_task_normalizes_share_and_path() -> None:
    task = build_task(
        taskname=" 名称 ",
        shareurl=" https://pan.quark.cn/s/abc?pwd=1234 ",
        savepath="video/tv/名称/",
        runweek=[1, 1, 7],
        enddate="2026-12-31",
        auto_unarchive=True,
    )
    assert task["taskname"] == "名称"
    assert task["shareurl"] == "https://pan.quark.cn/s/abc?pwd=1234"
    assert task["savepath"] == "/video/tv/名称"
    assert task["pattern"] == ".*"
    assert task["runweek"] == [1, 7]
    assert task["addition"]["auto_unarchive"]["enable"] is True


def test_name_from_share_uses_title_and_strips_path_chars() -> None:
    name = name_from_share(
        {"share": {"title": " 电影/名:字 "}},
        "https://pan.quark.cn/s/abc",
    )
    assert name == "电影 名 字"


def test_name_from_share_falls_back_to_share_id() -> None:
    assert name_from_share({"list": []}, "https://pan.quark.cn/s/abc?pwd=1") == "abc"


def test_build_task_rejects_root_and_non_quark_links() -> None:
    with pytest.raises(TaskError):
        build_task(taskname="名称", shareurl="https://example.com/s/abc", savepath="/video")
    with pytest.raises(TaskError):
        build_task(taskname="名称", shareurl="https://pan.quark.cn/s/abc", savepath="/")


def test_list_root_is_allowed() -> None:
    assert require_savepath("/", allow_root=True) == "/"


def test_apply_update_clears_ban_when_share_changes() -> None:
    updated = apply_update(
        {
            "taskname": "名称",
            "shareurl": "https://pan.quark.cn/s/old",
            "savepath": "/video",
            "shareurl_ban": "失效",
        },
        {"shareurl": "https://pan.quark.cn/s/new"},
    )
    assert updated["shareurl"] == "https://pan.quark.cn/s/new"
    assert "shareurl_ban" not in updated


def test_summarize_share_drops_stoken() -> None:
    summary = summarize_share(
        {
            "stoken": "secret",
            "share": {"title": "剧集"},
            "list": [
                {"file_name": "Season", "fid": "fid-1", "dir": True, "include_items": "01.mp4"},
                {"file_name": "01.mp4", "fid": "fid-2", "dir": False, "size": 10, "obj_category": "video"},
            ],
        },
        limit=1,
    )
    assert summary["title"] == "剧集"
    assert summary["total"] == 2
    assert summary["truncated"] == 1
    assert summary["files"] == [
        {"name": "Season", "fid": "fid-1", "is_dir": True, "include_items": "01.mp4"}
    ]
    assert "stoken" not in summary


def test_summarize_task_hides_plugin_payload() -> None:
    summary = summarize_task(
        {
            "taskname": "名称",
            "shareurl": "https://pan.quark.cn/s/abc",
            "savepath": "/video",
            "addition": {"emby": {"token": "secret"}, "auto_unarchive": {"enable": True}},
        }
    )
    assert summary["auto_unarchive"] is True
    assert "addition" not in summary
    assert "secret" not in str(summary)


def test_parse_sse_and_trim() -> None:
    log = parse_sse("data: 转存文件: a.mp4\n\ndata: [DONE]\n\n")
    assert log == "转存文件: a.mp4"
    trimmed = trim_log("a" * 30, limit=10)
    assert trimmed.startswith("aaaaa")
    assert "[truncated]" in trimmed
    assert trimmed.endswith("aaaaa")
