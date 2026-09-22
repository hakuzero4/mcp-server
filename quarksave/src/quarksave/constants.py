"""Shared constants for the quarksave MCP server."""

NAMESPACE = "quarksave"

INSTRUCTIONS = """\
Transfer Quark share links into a quark-auto-save instance (https://github.com/Cp0204/quark-auto-save).

Tools are namespaced as `quarksave_*`.

When the user gives a Quark link and asks to 转存 it, call `quarksave_save` with only the link.
Example: "把 https://pan.quark.cn/s/xxxx 转存到我的夸克"
→ quarksave_save(shareurl="https://pan.quark.cn/s/xxxx")

That reads the share title, saves the files into /{title}, and transfers once. Do not ask for a folder name.

Pass savepath only when the user names a directory.
Pass subscribe=true only when the user wants the link to keep updating (追更、订阅). Otherwise leave it false: one transfer, nothing stored.

A subdirectory link looks like `https://pan.quark.cn/s/xxxx#/list/share/{fid}`.
An extraction code looks like `https://pan.quark.cn/s/xxxx?pwd=1234`.

`pattern` filters and renames files. `.*` saves every file as-is. Names such as `$TV_MAGIC` come from `quarksave_list_tasks` → magic_regex.
This server does not change the Quark cookie, notify channels, or crontab, and it does not run every saved task at once.
"""
