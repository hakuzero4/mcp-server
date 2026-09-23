"""Shared constants for the tgchannel MCP server."""

NAMESPACE = "tgchannel"

INSTRUCTIONS = """\
Read public Telegram channels and public groups with the signed-in user account.

Tools are namespaced as `tgchannel_*`.

When the user gives a public channel link or @username and asks what it posted, call `tgchannel_list_messages` with that reference only.
Example: "看看 https://t.me/telegram 最近发了什么"
→ tgchannel_list_messages(channel="https://t.me/telegram")

Accept @name, t.me/name, t.me/s/name, and telegram.me/name.
Use `tgchannel_get_channel` for the profile. Use `tgchannel_search_messages` only to search inside that one channel.

Do not ask for a bot token. This server cannot send messages, join or leave channels, download media files, read private chats, or search all of Telegram.
If Telegram says the account must join first, tell the user. Do not try to join.
"""
