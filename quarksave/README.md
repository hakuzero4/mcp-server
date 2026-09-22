# quarksave

FastMCP 服务，调用 [quark-auto-save](https://github.com/Cp0204/quark-auto-save) 把夸克分享转存到自己的网盘。工具带 `quarksave_` 前缀。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `QAS_URL` | WebUI 地址，缺省 `http://127.0.0.1:5005`。也认 `QAS_BASE_URL` |
| `QAS_USERNAME` | WebUI 登录用户名 |
| `QAS_PASSWORD` | WebUI 登录密码 |
| `QAS_TIMEOUT` | 普通请求超时秒数，缺省 60 |
| `QAS_RUN_TIMEOUT` | 一次转存的超时秒数，缺省 900 |

密钥放在环境变量或本地 `.env`，不要提交。

```bash
uv sync --package quarksave
uv run --package quarksave quarksave
```

## Agent 用法

用户说「把 `https://pan.quark.cn/s/xxxx` 转存到 `/video/tv/名称`，以后继续追更」时，调用 `quarksave_save`：

```json
{
  "taskname": "名称",
  "shareurl": "https://pan.quark.cn/s/xxxx",
  "savepath": "/video/tv/名称",
  "subscribe": true
}
```

`subscribe` 为 false 时只转存一次，不写入任务列表，适合电影和已完结的剧。为 true 时写入任务，交给实例已有的定时规则，并立刻执行一次。

不熟悉的分享先调用 `quarksave_get_share`。要转存子目录时，把 `#/list/share/{fid}` 接到分享链接后面。提取码写成 `https://pan.quark.cn/s/xxxx?pwd=1234`。

`pattern` 用 `.*` 表示原样转存全部文件。`$TV_MAGIC` 这类名字来自 `quarksave_list_tasks` 返回的 `magic_regex`。

这个服务不改夸克 Cookie、通知渠道和定时规则。

## 测试

```bash
uv run --package quarksave pytest quarksave/tests
```
