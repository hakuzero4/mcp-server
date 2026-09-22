# quarksave

FastMCP 服务，调用 [quark-auto-save](https://github.com/Cp0204/quark-auto-save) 把夸克分享转存到自己的网盘。挂到网关后工具名带 `quarksave_` 前缀，例如 `quarksave_save`。

登录用 WebUI 的用户名和密码。服务会按 quark-auto-save 的规则算出接口凭证，调用方不需要再抄 API Token。返回结果里不含夸克 Cookie、通知配置和这个凭证。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `QAS_URL` | WebUI 地址，缺省 `http://127.0.0.1:5005`。也认 `QAS_BASE_URL` |
| `QAS_USERNAME` | WebUI 登录用户名。也认 `QAS_USER` |
| `QAS_PASSWORD` | WebUI 登录密码 |
| `QAS_TIMEOUT` | 普通请求超时秒数，缺省 60 |
| `QAS_RUN_TIMEOUT` | 一次转存的超时秒数，缺省 900。quark-auto-save 自身的任务超时缺省是 1800 |

密钥放在环境变量或仓库根目录的 `.env`，不要提交。

```bash
uv sync --package quarksave
uv run --package quarksave quarksave
```

跟其他服务一起跑时，在仓库根目录：

```bash
uv run python run.py all
```

容器使用根目录的 `.env`，`docker compose up -d` 即可。MCP 地址是 `http://<host>:8000/mcp`。

## 给 Agent

用户说「把 `https://pan.quark.cn/s/xxxx` 转存到我的夸克」时，只传链接：

```json
{
  "shareurl": "https://pan.quark.cn/s/xxxx"
}
```

`quarksave_save` 会读取分享标题，把文件转存到 `/{标题}`，只执行一次，不写入任务列表。标题里的 `\ / : * ? " < > |` 会换成空格。读不到标题时用分享 ID 当目录名。目录不存在时由 quark-auto-save 创建。

不要再向用户索要保存目录。下面几种情况才加参数：

| 用户还说了 | 额外参数 |
| --- | --- |
| 存到某个目录，例如 `/video/movie/名称` | `savepath` |
| 以后继续追更、订阅 | `subscribe: true` |
| 只要某一类文件，或要改名 | `pattern`、`replace` |
| 分享有提取码 | 链接写成 `https://pan.quark.cn/s/xxxx?pwd=1234`，`?pwd=` 放在 `#` 前面 |
| 只要分享里的某个子目录 | 链接写成 `https://pan.quark.cn/s/xxxx#/list/share/{fid}`。`fid` 来自 `quarksave_get_share` |

`pattern` 用 `.*` 表示原样转存全部文件。`$TV_MAGIC` 这类名字来自 `quarksave_list_tasks` 返回的 `magic_regex`。`subscribe: true` 会把任务交给实例已有的定时规则，并立刻转存一次。任务名重复时会拒绝，应改用 `quarksave_run_task` 或 `quarksave_update_task`。

这个服务不修改夸克 Cookie、通知渠道和定时规则，也不会一次跑完全部任务。删除任务不会删除网盘里已经转存的文件。

## 工具

| 工具 | 作用 |
| --- | --- |
| `quarksave_save` | 转存。只给 `shareurl` 即可。默认目录是 `/{分享标题}`，默认不订阅 |
| `quarksave_get_share` | 预览分享里的文件。可附带 `pattern`、`replace`、`savepath` 看重命名结果。默认最多返回 30 个文件 |
| `quarksave_list_save_path` | 查看网盘里某个目录已经有哪些文件。`/` 表示根目录 |
| `quarksave_search_shares` | 用实例上已启用的 CloudSaver 或 PanSou 搜索。没配搜索源时返回空列表 |
| `quarksave_list_tasks` | 已保存的任务、crontab，以及 `magic_regex` |
| `quarksave_get_task` | 按任务名读取一个任务 |
| `quarksave_run_task` | 立刻执行一个已保存的任务，不影响其他任务 |
| `quarksave_update_task` | 修改一个任务里给出的字段。更换 `shareurl` 会清掉失效标记 |
| `quarksave_delete_task` | 从任务列表删除。网盘文件保留 |

`quarksave_list_tasks` 里带 `shareurl_ban` 的任务，表示这条分享已经被标成失效。

## 资源和提示

| 名称 | 内容 |
| --- | --- |
| `qas://quarksave/tasks` | 已保存的任务、crontab、`magic_regex` |
| `quarksave_save_share_guide` | 提示：用户只给了一个链接时，只调用 `quarksave_save` |

## 测试

```bash
uv run --package quarksave pytest quarksave/tests
```
