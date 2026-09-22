"""Shared constants for the quarksave MCP server."""

NAMESPACE = "quarksave"

INSTRUCTIONS = """\
Transfer Quark share links into a quark-auto-save instance (https://github.com/Cp0204/quark-auto-save).

Tools are namespaced as `quarksave_*`.

When the user asks to 转存 a share, call `quarksave_save`.
Example: "把 https://pan.quark.cn/s/xxxx 转存到 /video/tv/名称，以后继续追更"
→ quarksave_save(taskname="名称", shareurl="https://pan.quark.cn/s/xxxx", savepath="/video/tv/名称", subscribe=true)

Use subscribe=false for a one-time transfer (a movie, or a series marked 完结 / 全集). The task is not stored.
Use subscribe=true for a series that is still updating. The task is stored for the instance crontab and run once immediately.

Before saving an unfamiliar share, call `quarksave_get_share` and pick a subdirectory.
Append `#/list/share/{fid}` to the share URL to save that folder.
Links that need an extraction code use `?pwd=xxxx` before the hash: `https://pan.quark.cn/s/xxxx?pwd=1234`.

`pattern` filters and renames files. `.*` saves every file as-is. Names such as `$TV_MAGIC` come from `quarksave_list_tasks` → magic_regex.
This server does not change the Quark cookie, notify channels, or crontab, and it does not run every saved task at once.
"""
