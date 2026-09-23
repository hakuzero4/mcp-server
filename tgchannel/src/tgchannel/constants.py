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

When the user gives specific post links, or asks to keep only certain posts, call `tgchannel_save_messages` with those links only.
Example: "把 https://t.me/telegram/123 和 https://t.me/telegram/456 存下来"
→ tgchannel_save_messages(messages=["https://t.me/telegram/123", "https://t.me/telegram/456"])
One post link can be `channel`: "把 https://t.me/telegram/123 这条存下来"
→ tgchannel_save_messages(channel="https://t.me/telegram/123")
Do not save the recent page in that case. Saving selected posts does not delete other saved rows.

When the user asks to save a channel's recent posts and does not name message ids, call `tgchannel_save_messages` with the channel link only.
Example: "把 https://t.me/telegram 最近的帖子存下来"
→ tgchannel_save_messages(channel="https://t.me/telegram")

Each saved post is one row keyed by `{username}:{message_id}`.
Saving the same post again overwrites that row. Identical content leaves `updated_at` unchanged.
A different message id is a different row.
Stored fields are username, id, date, edited, text, truncated, views, forwards, replies, pinned, media, file_name, grouped_id, author, action, and link.
Media files are not stored. Do not ask for a folder, a table, or a database schema.

"这个频道存了多少条" → tgchannel_count_saved(channel=...).
"存下来的最近几条" → tgchannel_list_saved(channel=...).
"在存下来的帖子里搜「关键词」" → tgchannel_search_saved(channel=..., query=...).
"取出 telegram:7" → tgchannel_get_saved(message="telegram:7").

Do not ask for a bot token. This server cannot send messages, join or leave channels, download media files, read private chats, or search all of Telegram.
If Telegram says the account must join first, tell the user. Do not try to join.
"""
