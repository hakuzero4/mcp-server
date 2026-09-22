"""Build, update, and summarize quark-auto-save transfer tasks."""

from __future__ import annotations

import re
from typing import Any

from quarksave.exceptions import TaskError

_SHARE_MARK = "pan.quark.cn/s/"
_ENDDATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TASK_FIELDS = (
    "taskname",
    "shareurl",
    "savepath",
    "pattern",
    "replace",
    "enddate",
    "runweek",
    "ignore_extension",
    "update_subdir",
    "shareurl_ban",
)
_LOG_LIMIT = 20_000


def require_taskname(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise TaskError("taskname is required")
    if len(cleaned) > 200:
        raise TaskError("taskname is too long")
    return cleaned


def require_shareurl(value: str) -> str:
    cleaned = value.strip()
    if _SHARE_MARK not in cleaned:
        raise TaskError(
            "shareurl must be a Quark share link, for example https://pan.quark.cn/s/xxxx"
        )
    return cleaned


def require_savepath(value: str, *, allow_root: bool = False) -> str:
    cleaned = re.sub(r"/+", "/", value.strip().replace("\\", "/"))
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    if cleaned != "/":
        cleaned = cleaned.rstrip("/")
    if cleaned == "/" and not allow_root:
        raise TaskError("savepath must be a directory such as /video/tv/Name")
    return cleaned


def require_enddate(value: str) -> str:
    cleaned = value.strip()
    if not _ENDDATE.fullmatch(cleaned):
        raise TaskError("enddate must be YYYY-MM-DD")
    return cleaned


def require_runweek(days: list[int]) -> list[int]:
    if not days:
        raise TaskError("runweek must list weekdays from 1 (Monday) to 7 (Sunday)")
    cleaned: list[int] = []
    for day in days:
        if not isinstance(day, int) or isinstance(day, bool) or day not in range(1, 8):
            raise TaskError("runweek days must be integers 1 (Monday) through 7 (Sunday)")
        if day not in cleaned:
            cleaned.append(day)
    return cleaned


def require_limit(value: int, *, upper: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > upper:
        raise TaskError(f"limit must be an integer from 1 to {upper}")
    return value


def build_task(
    *,
    taskname: str,
    shareurl: str,
    savepath: str,
    pattern: str = ".*",
    replace: str = "",
    ignore_extension: bool = False,
    runweek: list[int] | None = None,
    enddate: str | None = None,
    update_subdir: str = "",
    auto_unarchive: bool = False,
) -> dict[str, Any]:
    """Build the task object quark-auto-save expects for a transfer."""
    task: dict[str, Any] = {
        "taskname": require_taskname(taskname),
        "shareurl": require_shareurl(shareurl),
        "savepath": require_savepath(savepath),
        "pattern": pattern,
        "replace": replace,
    }
    if ignore_extension:
        task["ignore_extension"] = True
    if runweek is not None:
        task["runweek"] = require_runweek(runweek)
    if enddate:
        task["enddate"] = require_enddate(enddate)
    if update_subdir.strip():
        task["update_subdir"] = update_subdir.strip()
    if auto_unarchive:
        task["addition"] = {
            "auto_unarchive": {
                "enable": True,
                "auto_clean": True,
                "auto_clean_zipdir": True,
            }
        }
    return task


def apply_update(task: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `task` with the provided fields replaced."""
    updated = dict(task)
    if changes.get("taskname") is not None:
        updated["taskname"] = require_taskname(changes["taskname"])
    if changes.get("shareurl") is not None:
        updated["shareurl"] = require_shareurl(changes["shareurl"])
        updated.pop("shareurl_ban", None)
    if changes.get("savepath") is not None:
        updated["savepath"] = require_savepath(changes["savepath"])
    if changes.get("pattern") is not None:
        updated["pattern"] = changes["pattern"]
    if changes.get("replace") is not None:
        updated["replace"] = changes["replace"]
    if changes.get("ignore_extension") is not None:
        updated["ignore_extension"] = bool(changes["ignore_extension"])
    if changes.get("runweek") is not None:
        updated["runweek"] = require_runweek(changes["runweek"])
    if changes.get("clear_runweek"):
        updated.pop("runweek", None)
    if changes.get("enddate") is not None:
        updated["enddate"] = require_enddate(changes["enddate"])
    if changes.get("clear_enddate"):
        updated.pop("enddate", None)
    if changes.get("update_subdir") is not None:
        text = str(changes["update_subdir"]).strip()
        if text:
            updated["update_subdir"] = text
        else:
            updated.pop("update_subdir", None)
    if changes.get("clear_shareurl_ban"):
        updated.pop("shareurl_ban", None)
    return updated


def find_task(tasks: list[dict[str, Any]], taskname: str) -> tuple[int, dict[str, Any]]:
    name = require_taskname(taskname)
    matches = [(index, task) for index, task in enumerate(tasks) if task.get("taskname") == name]
    if not matches:
        raise TaskError(f"No task named {name!r}.")
    if len(matches) > 1:
        raise TaskError(
            f"Multiple tasks named {name!r}. Rename the extras in the WebUI before changing them here."
        )
    return matches[0]


def summarize_task(task: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "taskname": task.get("taskname"),
        "shareurl": task.get("shareurl"),
        "savepath": task.get("savepath"),
    }
    for key in _TASK_FIELDS:
        if key in summary:
            continue
        value = task.get(key)
        if value not in (None, "", []):
            summary[key] = value
    addition = task.get("addition")
    if isinstance(addition, dict):
        unarchive = addition.get("auto_unarchive")
        if isinstance(unarchive, dict) and unarchive.get("enable"):
            summary["auto_unarchive"] = True
    return summary


def summarize_file(item: dict[str, Any]) -> dict[str, Any]:
    info: dict[str, Any] = {
        "name": item.get("file_name"),
        "fid": item.get("fid"),
        "is_dir": bool(item.get("dir")),
    }
    if info["is_dir"]:
        if item.get("include_items"):
            info["include_items"] = item.get("include_items")
    else:
        if item.get("size") not in (None, ""):
            info["size"] = item.get("size")
        if item.get("obj_category"):
            info["type"] = item.get("obj_category")
    if item.get("file_name_re"):
        info["renamed"] = item.get("file_name_re")
    if item.get("file_name_saved"):
        info["already_saved"] = item.get("file_name_saved")
    return info


def _clip_files(files: list[dict[str, Any]], limit: int) -> tuple[list[dict[str, Any]], int]:
    shown = [summarize_file(item) for item in files[:limit]]
    hidden = max(len(files) - limit, 0)
    return shown, hidden


def summarize_share(data: dict[str, Any], *, limit: int) -> dict[str, Any]:
    files = data.get("list") if isinstance(data.get("list"), list) else []
    share = data.get("share") if isinstance(data.get("share"), dict) else {}
    shown, hidden = _clip_files(files, limit)
    result: dict[str, Any] = {
        "title": share.get("title") or data.get("title"),
        "total": len(files),
        "paths": data.get("paths") or [],
        "files": shown,
    }
    if hidden:
        result["truncated"] = hidden
    return result


def summarize_directory(data: dict[str, Any], *, path: str, limit: int) -> dict[str, Any]:
    files = data.get("list") if isinstance(data.get("list"), list) else []
    paths = data.get("paths") if isinstance(data.get("paths"), list) else []
    names = [str(item.get("name")) for item in paths if isinstance(item, dict) and item.get("name")]
    resolved = "/" + "/".join(names) if names else path
    shown, hidden = _clip_files(files, limit)
    result: dict[str, Any] = {
        "path": resolved,
        "fid": data.get("fid"),
        "total": len(files),
        "files": shown,
    }
    if hidden:
        result["truncated"] = hidden
    return result


def summarize_search_hit(item: dict[str, Any]) -> dict[str, Any]:
    hit: dict[str, Any] = {
        "taskname": item.get("taskname") or "",
        "shareurl": item.get("shareurl") or "",
        "content": item.get("content") or "",
        "datetime": item.get("datetime") or "",
        "source": item.get("source") or "",
    }
    if item.get("channel"):
        hit["channel"] = item.get("channel")
    if item.get("tags"):
        hit["tags"] = item.get("tags")
    return hit


def parse_sse(text: str) -> str:
    """Collect `data:` lines from a quark-auto-save run stream."""
    lines: list[str] = []
    for raw in text.splitlines():
        if not raw.startswith("data:"):
            continue
        content = raw[5:].lstrip()
        if content == "[DONE]":
            continue
        lines.append(content)
    return "\n".join(lines).strip()


def trim_log(text: str, limit: int = _LOG_LIMIT) -> str:
    if len(text) <= limit:
        return text
    head = limit // 2
    tail = limit - head
    return f"{text[:head]}\n...[truncated]...\n{text[-tail:]}"
