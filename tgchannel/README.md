# tgchannel

FastMCP 服务，用已登录的 Telegram **用户账号**读取公共频道和公开群，并把帖子存进本地 SQLite。挂到网关后工具名带 `tgchannel_` 前缀，例如 `tgchannel_list_messages`、`tgchannel_save_messages`。

Bot 读不了任意公共频道的历史，所以这里不用 Bot token。对 Telegram 只读：不发消息、不加频道、不退频道、不下载媒体文件、不读私聊，也不在全站搜索。保存只写本地库。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `TG_API_ID` | [my.telegram.org](https://my.telegram.org) 里应用的 `api_id` |
| `TG_API_HASH` | 同一个应用的 `api_hash` |
| `TG_SESSION` | 一次性登录打出来的会话字符串。没有手机号和两步验证密码 |
| `TG_TIMEOUT` | 一次工具调用的超时秒数，含连接。缺省 30 |
| `TG_STORE_PATH` | 已存帖子的 SQLite 文件。留空时只有保存和读取存档的工具报错 |

密钥放在环境变量或仓库根目录的 `.env`，不要提交。`api_hash` 和 `TG_SESSION` 都不要贴到聊天里。

留空 `TG_API_ID`、`TG_API_HASH`、`TG_SESSION` 时，读取 Telegram 的工具会报错，同进程里的其他 MCP 仍能启动。`TG_STORE_PATH` 留空时，读频道仍然可用，保存和查存档会报 `Set TG_STORE_PATH.`

## 一次性登录

在本机仓库根目录执行（需要能交互输入，不要在容器里跑）：

```bash
uv run python -m tgchannel.login
```

用将要读频道的那个用户账号。验证码发到 Telegram。如果开了两步验证，密码只在这次输入。把打印出的一行写进 `.env`：

```bash
TG_API_ID=123456
TG_API_HASH=
TG_SESSION=
```

上面的数字是占位。应用名称可以填 `mcp-server`，平台选 Desktop。频道本身不用加 Bot。

跟其他服务一起跑：

```bash
uv run python run.py all
```

容器使用根目录的 `.env`，`docker compose up -d` 即可。MCP 地址是 `http://<host>:8000/mcp`。

## 给 Agent

用户说「看看 `https://t.me/telegram` 最近发了什么」时，只传链接或 `@用户名`：

```json
{
  "channel": "https://t.me/telegram"
}
```

`tgchannel_list_messages` 默认返回最新 20 条，单次最多 100 条。接受 `@name`、`t.me/name`、`t.me/s/name`、`telegram.me/name`。帖子链接里的消息 id 会被忽略，读的是整个频道。

| 用户还说了 | 调用 |
| --- | --- |
| 这个频道是做什么的、多少人 | `tgchannel_get_channel` |
| 在这个频道里搜某个词 | `tgchannel_search_messages`，只搜这一个频道 |
| 再往前翻 | `tgchannel_list_messages`，把上一批最小的 `id` 传给 `offset_id` |
| 把 `https://t.me/telegram` 最近的帖子存下来 | `tgchannel_save_messages`，只传频道链接 |
| 把 `https://t.me/telegram/123` 和 `https://t.me/telegram/456` 存下来 | `tgchannel_save_messages`，`messages` 只放这几条帖子链接 |
| 这个频道存了多少条 | `tgchannel_count_saved` |
| 存下来的最近几条 | `tgchannel_list_saved` |
| 在存下来的帖子里搜「关键词」 | `tgchannel_search_saved`，只搜这个频道的存档 |
| 取出 `telegram:7` | `tgchannel_get_saved`，`message` 为 `telegram:7` 或帖子链接 |

存档按 `用户名 + 消息 id` 区分。同一条再存一次还是一行：内容没变是 `unchanged`，浏览数或正文变了就覆盖。消息 id 不同是另一行。

只想留下个别帖子时，把帖子链接放进 `messages`，例如 `https://t.me/telegram/123`。这样只保存这几条，不会把最近一页一起写入，也不会删掉库里已经有的其它帖子。单条链接可以直接当 `channel`。频道链接（没有消息 id）仍然保存最近一页，默认 20 条。

每条保存这些字段：`username`、`id`、`date`、`edited`、`text`（最长 4000 字）、`truncated`、`views`、`forwards`、`replies`、`pinned`、`media`、`file_name`、`grouped_id`、`author`、`action`、`link`。另外 `saved_at` 和 `updated_at` 由库自己写。列表和搜索里的 `text` 只给前 200 字，完整正文用 `tgchannel_get_saved`。频道标题、简介、订阅人数不在帖子里。媒体只留类型和文件名。

私有邀请（`t.me/+...`、`joinchat`、`t.me/c/...`）会直接拒绝。解析结果如果是个人账号，也会拒绝。

Telegram 若要求先加入才能看历史，工具返回错误，不会自动加入。限流时返回需要等待的秒数，不会在服务里空等。

一条帖子包含 id、时间、文本（超过 4000 字会截断）、浏览 / 转发 / 回复数、媒体类型和文件名、以及 `https://t.me/<用户名>/<id>`。相册会按 `grouped_id` 分成多条。不返回文件内容。

## 工具

| 工具 | 作用 |
| --- | --- |
| `tgchannel_get_channel` | 标题、简介、用户名、订阅数、是频道还是公开群、链接 |
| `tgchannel_list_messages` | 最近帖子。`limit` 默认 20，最大 100。`offset_id` 为 0 时从最新一条开始 |
| `tgchannel_search_messages` | 在给出的这一个公共频道里搜索。`query` 必填 |
| `tgchannel_save_messages` | 频道链接保存最近一页，默认 20 条，最多 100。帖子链接或 `messages` 只保存点名的帖子。同一条覆盖原行 |
| `tgchannel_list_saved` | 已存帖子，按发帖时间从新到旧。`text` 最多 200 字 |
| `tgchannel_count_saved` | 这个频道已存的条数 |
| `tgchannel_search_saved` | 在这个频道的存档里按正文子串搜索。`%` 和 `_` 是字面字符 |
| `tgchannel_get_saved` | 按 `telegram:7` 或帖子链接取完整一条 |

本机直接跑时在 `.env` 写 `TG_STORE_PATH=data/tgchannel.sqlite`。`data/` 已忽略。容器里 Compose 固定为 `/data/tgchannel.sqlite`，卷是 `./data:/data`。Linux 宿主机上这个目录需要 uid 1000 可写。卷要挂目录，WAL 会在库旁边产生 `-wal` 和 `-shm`。

## 测试

```bash
uv run --package tgchannel pytest tgchannel/tests
```

测试不连接 Telegram。
