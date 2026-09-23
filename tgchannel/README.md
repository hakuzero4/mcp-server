# tgchannel

FastMCP 服务，用已登录的 Telegram **用户账号**读取公共频道和公开群。挂到网关后工具名带 `tgchannel_` 前缀，例如 `tgchannel_list_messages`。

Bot 读不了任意公共频道的历史，所以这里不用 Bot token。服务只读：不发消息、不加频道、不退频道、不下载媒体文件、不读私聊，也不在全站搜索。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `TG_API_ID` | [my.telegram.org](https://my.telegram.org) 里应用的 `api_id` |
| `TG_API_HASH` | 同一个应用的 `api_hash` |
| `TG_SESSION` | 一次性登录打出来的会话字符串。没有手机号和两步验证密码 |
| `TG_TIMEOUT` | 一次工具调用的超时秒数，含连接。缺省 30 |

密钥放在环境变量或仓库根目录的 `.env`，不要提交。`api_hash` 和 `TG_SESSION` 都不要贴到聊天里。

留空这三项时，本服务的工具会报错，同进程里的其他 MCP 仍能启动。

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

私有邀请（`t.me/+...`、`joinchat`、`t.me/c/...`）会直接拒绝。解析结果如果是个人账号，也会拒绝。

Telegram 若要求先加入才能看历史，工具返回错误，不会自动加入。限流时返回需要等待的秒数，不会在服务里空等。

一条帖子包含 id、时间、文本（超过 4000 字会截断）、浏览 / 转发 / 回复数、媒体类型和文件名、以及 `https://t.me/<用户名>/<id>`。相册会按 `grouped_id` 分成多条。不返回文件内容。

## 工具

| 工具 | 作用 |
| --- | --- |
| `tgchannel_get_channel` | 标题、简介、用户名、订阅数、是频道还是公开群、链接 |
| `tgchannel_list_messages` | 最近帖子。`limit` 默认 20，最大 100。`offset_id` 为 0 时从最新一条开始 |
| `tgchannel_search_messages` | 在给出的这一个公共频道里搜索。`query` 必填 |

## 测试

```bash
uv run --package tgchannel pytest tgchannel/tests
```

测试不连接 Telegram。
