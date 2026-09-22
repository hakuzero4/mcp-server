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

用户说「把 `https://pan.quark.cn/s/xxxx` 转存到我的夸克」时，只传链接：

```json
{
  "shareurl": "https://pan.quark.cn/s/xxxx"
}
```

工具读取分享标题，把文件转存到 `/{标题}`，只执行一次，不写入任务列表。

用户指定了目录时再传 `savepath`。用户说要追更时再传 `subscribe: true`。子目录把 `#/list/share/{fid}` 接到链接后面。提取码写成 `https://pan.quark.cn/s/xxxx?pwd=1234`。

`pattern` 用 `.*` 表示原样转存全部文件。`$TV_MAGIC` 这类名字来自 `quarksave_list_tasks` 返回的 `magic_regex`。

这个服务不改夸克 Cookie、通知渠道和定时规则。

## 测试

```bash
uv run --package quarksave pytest quarksave/tests
```
