"""Transfer tools for quark-auto-save."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from quarksave.deps import call, checked, qas
from quarksave.exceptions import QasApiError
from quarksave.tasks import (
    apply_update,
    build_task,
    find_task,
    name_from_share,
    require_limit,
    require_savepath,
    require_shareurl,
    require_taskname,
    summarize_directory,
    summarize_search_hit,
    summarize_share,
    summarize_task,
)

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, openWorldHint=True, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    openWorldHint=True,
    idempotentHint=True,
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def list_tasks(ctx: Context) -> dict[str, Any]:
        """List saved transfer tasks, the crontab, and magic rename patterns.

        Cookie, notify settings, and the API token are omitted.
        `shareurl_ban` is set when quark-auto-save has marked that share invalid.
        """
        return await call(qas(ctx).public_state())

    @mcp.tool(annotations=READ)
    async def get_task(ctx: Context, taskname: str) -> dict[str, Any]:
        """Get one saved transfer task by its exact task name."""
        tasks = await call(qas(ctx).tasklist())
        _, task = checked(find_task, tasks, taskname)
        return summarize_task(task)

    @mcp.tool(annotations=READ)
    async def get_share(
        ctx: Context,
        shareurl: str,
        limit: int = 30,
        taskname: str | None = None,
        savepath: str | None = None,
        pattern: str | None = None,
        replace: str | None = None,
    ) -> dict[str, Any]:
        """Preview a Quark share before transferring it.

        Args:
            shareurl: Quark share URL. Add `#/list/share/{fid}` to open a subdirectory.
            limit: Maximum files to return, from 1 to 200.
            taskname: Optional. With pattern/replace/savepath, preview renamed names.
            savepath: Optional save directory used for the rename preview.
            pattern: Optional filename filter, for example `.*` or `$TV_MAGIC`.
            replace: Optional replacement, for example `{TASKNAME}.S01E{E}.{EXT}`.
        """
        cleaned = checked(require_shareurl, shareurl)
        checked(require_limit, limit, upper=200)
        preview: dict[str, Any] | None = None
        if any(value is not None for value in (taskname, savepath, pattern, replace)):
            preview = {}
            if taskname is not None:
                preview["taskname"] = taskname
            if savepath is not None:
                preview["savepath"] = checked(require_savepath, savepath)
            if pattern is not None:
                preview["pattern"] = pattern
            if replace is not None:
                preview["replace"] = replace
        data = await call(qas(ctx).share_detail(cleaned, preview))
        return summarize_share(data, limit=limit)

    @mcp.tool(annotations=READ)
    async def list_save_path(ctx: Context, path: str, limit: int = 30) -> dict[str, Any]:
        """List files already stored at a Quark directory.

        Args:
            path: Directory in the signed-in Quark drive, for example `/video/tv/Name`.
            limit: Maximum files to return, from 1 to 200.
        """
        savepath = checked(require_savepath, path, allow_root=True)
        checked(require_limit, limit, upper=200)
        data = await call(qas(ctx).savepath_detail(savepath))
        return summarize_directory(data, path=savepath, limit=limit)

    @mcp.tool(annotations=READ)
    async def search_shares(
        ctx: Context,
        query: str,
        deep: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search shares configured on the quark-auto-save instance.

        Requires CloudSaver or PanSou to be enabled in that instance.
        An empty list means those sources are off or nothing matched.

        Args:
            query: Title or keyword.
            deep: Ask PanSou to refresh instead of using its cache.
            limit: Maximum hits to return, from 1 to 50.
        """
        text = query.strip()
        if not text:
            raise ToolError("query is required")
        checked(require_limit, limit, upper=50)
        hits = await call(qas(ctx).search(text, deep=deep))
        shown = [summarize_search_hit(item) for item in hits[:limit]]
        result: dict[str, Any] = {"total": len(hits), "shares": shown}
        if len(hits) > limit:
            result["truncated"] = len(hits) - limit
        return result

    @mcp.tool(annotations=WRITE)
    async def save(
        ctx: Context,
        shareurl: str,
        savepath: str | None = None,
        taskname: str | None = None,
        subscribe: bool = False,
        pattern: str = ".*",
        replace: str = "",
        ignore_extension: bool = False,
        runweek: list[int] | None = None,
        enddate: str | None = None,
        update_subdir: str = "",
        auto_unarchive: bool = False,
    ) -> dict[str, Any]:
        """Transfer a Quark share into the account. A share link is enough.

        Use this when the user says "把这个链接转存到我的夸克".
        Call quarksave_save(shareurl="https://pan.quark.cn/s/xxxx") and nothing else.
        The share title becomes the folder name, for example /电影名, and the files
        are transferred once. The task is not stored.

        Pass savepath only when the user names a directory.
        Pass subscribe=true only when the user wants 追更. The task name must be new.

        Args:
            shareurl: `https://pan.quark.cn/s/xxxx`, optional `?pwd=` and `#/list/share/{fid}`.
            savepath: Destination directory. Omit to use /{share title}.
            taskname: Display name. Omit to use the share title.
            subscribe: Store the task and keep updating it on the crontab.
            pattern: Filename filter. `.*` saves everything. `$TV_MAGIC` uses a saved magic regex.
            replace: New filename. Empty keeps the original name when pattern is not magic.
            ignore_extension: Treat `01.mp4` and `01.mkv` as the same episode.
            runweek: Weekdays to run a subscription, 1 Monday through 7 Sunday.
            enddate: Stop running after this date, `YYYY-MM-DD`.
            update_subdir: Regex of subfolders to follow inside the share.
            auto_unarchive: Unpack zip/rar/7z after saving and remove the archive.
        """
        if not taskname or not savepath:
            detail = await call(qas(ctx).share_detail(checked(require_shareurl, shareurl)))
            derived = checked(name_from_share, detail, shareurl)
            taskname = taskname or derived
            savepath = savepath or f"/{derived}"
        taskname = checked(require_taskname, taskname)
        savepath = checked(require_savepath, savepath)
        task = checked(
            build_task,
            taskname=taskname,
            shareurl=shareurl,
            savepath=savepath,
            pattern=pattern,
            replace=replace,
            ignore_extension=ignore_extension,
            runweek=runweek,
            enddate=enddate,
            update_subdir=update_subdir,
            auto_unarchive=auto_unarchive,
        )
        client = qas(ctx)
        stored = False
        running = task
        if subscribe:
            existing = await call(client.tasklist())
            if any(item.get("taskname") == task["taskname"] for item in existing):
                raise ToolError(
                    f"Task {task['taskname']!r} already exists. "
                    "Use run_task to transfer it again, or update_task to change it."
                )
            running = await call(client.add_task(task))
            stored = True
        try:
            log = await client.run_tasks([running])
        except QasApiError as exc:
            message = str(exc)
            if stored:
                message = (
                    f"Task {task['taskname']!r} was saved, but the transfer failed: {exc}"
                )
            raise ToolError(message) from exc
        return {
            "taskname": task["taskname"],
            "shareurl": task["shareurl"],
            "savepath": task["savepath"],
            "subscribed": stored,
            "pattern": task["pattern"],
            "replace": task["replace"],
            "log": log,
        }

    @mcp.tool(annotations=WRITE)
    async def run_task(ctx: Context, taskname: str) -> dict[str, Any]:
        """Run one saved transfer task now.

        Does not run the other tasks. Use save for a share that is not stored yet.
        """
        client = qas(ctx)
        tasks = await call(client.tasklist())
        _, task = checked(find_task, tasks, taskname)
        log = await call(client.run_tasks([task]))
        return {
            "taskname": task.get("taskname"),
            "shareurl": task.get("shareurl"),
            "savepath": task.get("savepath"),
            "log": log,
        }

    @mcp.tool(annotations=WRITE)
    async def update_task(
        ctx: Context,
        taskname: str,
        new_taskname: str | None = None,
        shareurl: str | None = None,
        savepath: str | None = None,
        pattern: str | None = None,
        replace: str | None = None,
        ignore_extension: bool | None = None,
        runweek: list[int] | None = None,
        clear_runweek: bool = False,
        enddate: str | None = None,
        clear_enddate: bool = False,
        update_subdir: str | None = None,
        clear_shareurl_ban: bool = False,
    ) -> dict[str, Any]:
        """Change fields on one saved task. Omitted fields stay as they are.

        Changing shareurl, or clear_shareurl_ban=true, clears an invalid-link mark
        so the task can run again. Call run_task afterwards to transfer immediately.

        Args:
            taskname: Current task name.
            new_taskname: Rename the task.
            shareurl: Replacement Quark share URL.
            savepath: Replacement destination directory.
            pattern: Replacement filename filter.
            replace: Replacement filename template.
            ignore_extension: Compare episodes without the file extension.
            runweek: Weekdays 1 (Monday) through 7 (Sunday).
            clear_runweek: Run on every day again.
            enddate: Last day to run, YYYY-MM-DD.
            clear_enddate: Remove the end date.
            update_subdir: Subfolder regex. Pass an empty string to clear it.
            clear_shareurl_ban: Clear the invalid-link mark without changing the URL.
        """
        client = qas(ctx)
        tasks = await call(client.tasklist())
        index, current = checked(find_task, tasks, taskname)
        updated = checked(
            apply_update,
            current,
            {
                "taskname": new_taskname,
                "shareurl": shareurl,
                "savepath": savepath,
                "pattern": pattern,
                "replace": replace,
                "ignore_extension": ignore_extension,
                "runweek": runweek,
                "clear_runweek": clear_runweek,
                "enddate": enddate,
                "clear_enddate": clear_enddate,
                "update_subdir": update_subdir,
                "clear_shareurl_ban": clear_shareurl_ban,
            },
        )
        if updated.get("taskname") != current.get("taskname"):
            for other in tasks:
                if other is not current and other.get("taskname") == updated.get("taskname"):
                    raise ToolError(f"Task {updated['taskname']!r} already exists.")
        tasks[index] = updated
        await call(client.replace_tasklist(tasks))
        return summarize_task(updated)

    @mcp.tool(annotations=DESTRUCTIVE)
    async def delete_task(ctx: Context, taskname: str) -> dict[str, Any]:
        """Delete one saved transfer task. Files already in Quark are left in place."""
        client = qas(ctx)
        tasks = await call(client.tasklist())
        index, task = checked(find_task, tasks, taskname)
        remaining = [item for item_index, item in enumerate(tasks) if item_index != index]
        await call(client.replace_tasklist(remaining))
        return {"deleted": task.get("taskname")}

    @mcp.resource("qas://tasks", mime_type="application/json")
    async def tasks_resource(ctx: Context) -> dict[str, Any]:
        """Saved transfer tasks, crontab, and magic rename patterns."""
        return await call(qas(ctx).public_state())

    @mcp.prompt
    def save_share_guide(shareurl: str) -> str:
        """Guide for transferring one Quark share when the user only sends a link."""
        return (
            f"Transfer `{shareurl}` into the user's Quark drive.\n\n"
            "Call `quarksave_save` with only that shareurl.\n"
            "The tool names the folder from the share title and transfers the files once.\n"
            "Read the returned log for lines starting with 转存文件 or a failure mark."
        )
