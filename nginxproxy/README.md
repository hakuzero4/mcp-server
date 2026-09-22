# nginxproxy

FastMCP 服务，封装 [Nginx Proxy Manager](https://nginxproxymanager.com) 的 REST API。挂到网关后工具名带 `nginxproxy_` 前缀，例如 `nginxproxy_create_service`。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `NPM_URL` | 管理界面地址，缺省 `http://127.0.0.1:81`。没有 `/api` 会自动补上 |
| `NPM_EMAIL` | 登录邮箱 |
| `NPM_PASSWORD` | 登录密码 |
| `NPM_TOKEN` | 可选。已有 JWT 时先用它，过期后若配了账号密码会重新登录 |
| `NPM_TIMEOUT` | 普通请求超时秒数，缺省 30 |
| `NPM_CERT_TIMEOUT` | Let's Encrypt 签发和续期的超时秒数，缺省 900 |

密钥放在环境变量或仓库根目录的 `.env`，不要提交。

```bash
uv sync --package nginxproxy
uv run --package nginxproxy nginxproxy
```

跟其他服务一起跑时，在仓库根目录：

```bash
uv run python run.py all
```

容器使用根目录的 `.env`，`docker compose up -d` 即可。MCP 地址是 `http://<host>:8000/mcp`。

## 给 Agent

用户说「帮我创建一个服务 `10.0.0.10` 的 `8080` 端口，启用自定义证书，域名为 `app.home.com`」时，调用 `nginxproxy_create_service`：

```json
{
  "domain": "app.home.com",
  "ip": "10.0.0.10",
  "port": 8080,
  "use_custom_certificate": true
}
```

工具会找已经上传的自定义证书或通配符证书（`*.home.com` 只匹配一层子域），绑到这个反代上，并强制跳转到 HTTPS。同名域名已存在时会拒绝创建。这个流程不要去申请 Let's Encrypt。

需要指定某一张证书时传 `certificate_id` 或 `certificate_name`。上游走 HTTPS 时传 `forward_scheme: "https"`。要 WebSocket 时传 `websocket: true`。

更细的字段用 `nginxproxy_create_proxy_host` 和 `nginxproxy_update_proxy_host`。

## 工具

### 反代

| 工具 | 作用 |
| --- | --- |
| `nginxproxy_create_service` | 用域名、上游 IP、端口创建反代。默认绑定已上传的自定义证书并强制 HTTPS |
| `nginxproxy_list_proxy_hosts` | 列出反代。`query` 按域名过滤，`expand` 可带 `owner`、`certificate`、`access_list` |
| `nginxproxy_get_proxy_host` | 按 id 读取一个反代 |
| `nginxproxy_create_proxy_host` | 按 NPM 字段创建反代。`certificate_id` 为 `0` 表示不挂证书，`"new"` 表示申请 Let's Encrypt |
| `nginxproxy_update_proxy_host` | 修改一个反代，未传的字段保持原样 |
| `nginxproxy_enable_proxy_host` | 启用 |
| `nginxproxy_disable_proxy_host` | 停用 |
| `nginxproxy_delete_proxy_host` | 删除 |

### 证书

| 工具 | 作用 |
| --- | --- |
| `nginxproxy_list_certificates` | 列出证书 |
| `nginxproxy_get_certificate` | 按 id 读取一张证书 |
| `nginxproxy_list_dns_providers` | 列出 DNS 验证提供商 |
| `nginxproxy_test_certificate_http` | 检查域名的 HTTP 验证是否可达 |
| `nginxproxy_create_letsencrypt_certificate` | 申请 Let's Encrypt 证书 |
| `nginxproxy_create_custom_certificate` | 上传自定义证书 |
| `nginxproxy_renew_certificate` | 续期 |
| `nginxproxy_delete_certificate` | 删除 |

`nginxproxy_create_service` 只会选用 `provider` 为 `other` 的已上传证书。

### 跳转、404、四层转发

这三类各有 list、get、create、update、enable、disable、delete。

| 对象 | 工具 |
| --- | --- |
| 域名跳转 | `nginxproxy_list_redirection_hosts`、`nginxproxy_get_redirection_host`、`nginxproxy_create_redirection_host`、`nginxproxy_update_redirection_host`、`nginxproxy_enable_redirection_host`、`nginxproxy_disable_redirection_host`、`nginxproxy_delete_redirection_host` |
| 自定义 404 | `nginxproxy_list_dead_hosts`、`nginxproxy_get_dead_host`、`nginxproxy_create_dead_host`、`nginxproxy_update_dead_host`、`nginxproxy_enable_dead_host`、`nginxproxy_disable_dead_host`、`nginxproxy_delete_dead_host` |
| TCP/UDP 转发 | `nginxproxy_list_streams`、`nginxproxy_get_stream`、`nginxproxy_create_stream`、`nginxproxy_update_stream`、`nginxproxy_enable_stream`、`nginxproxy_disable_stream`、`nginxproxy_delete_stream` |

### 访问控制

| 工具 | 作用 |
| --- | --- |
| `nginxproxy_list_access_lists` | 列出访问列表 |
| `nginxproxy_get_access_list` | 按 id 读取 |
| `nginxproxy_create_access_list` | 创建。可带 HTTP 基本认证用户和 IP allow/deny |
| `nginxproxy_update_access_list` | 修改 |
| `nginxproxy_delete_access_list` | 删除 |

反代上的 `access_list_id` 为 `0` 表示公开。

### 实例

| 工具 | 作用 |
| --- | --- |
| `nginxproxy_get_status` | API 是否可用 |
| `nginxproxy_get_hosts_report` | 各类主机数量 |
| `nginxproxy_get_audit_log` | 审计日志 |
| `nginxproxy_list_users` | 列出用户 |
| `nginxproxy_get_user` | 按 id 读取用户 |
| `nginxproxy_list_settings` | 列出设置 |
| `nginxproxy_get_setting` | 读取一项设置 |
| `nginxproxy_update_setting` | 修改一项设置 |

## 资源和提示

挂到网关后资源 URI 带 namespace：

| URI | 内容 |
| --- | --- |
| `npm://nginxproxy/status` | API 状态 |
| `npm://nginxproxy/proxy-hosts` | 全部反代 |
| `npm://nginxproxy/proxy-hosts/{host_id}` | 一个反代 |
| `npm://nginxproxy/certificates` | 全部证书 |
| `npm://nginxproxy/report` | 主机数量 |

提示 `nginxproxy_create_https_proxy_guide` 用来生成「域名 + 上游 + 自定义证书」的调用说明。

## 测试

```bash
uv run --package nginxproxy pytest nginxproxy/tests
```
