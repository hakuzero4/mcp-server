# nginxproxy

FastMCP 服务，封装 [Nginx Proxy Manager](https://nginxproxymanager.com) REST API。工具带 `nginxproxy_` 前缀。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `NPM_URL` | 管理界面地址，缺省 `http://127.0.0.1:81`。没有 `/api` 会自动补上 |
| `NPM_EMAIL` | 登录邮箱 |
| `NPM_PASSWORD` | 登录密码 |
| `NPM_TOKEN` | 可选，已有 JWT。过期后若配置了账号密码会重新登录 |

密钥放在环境变量或本地 `.env`，不要提交。

```bash
uv sync --package nginxproxy
uv run --package nginxproxy nginxproxy
```

容器内：

```bash
docker run --rm -p 8000:8000 \
  -e MCP_SERVER=all \
  -e NPM_URL=http://127.0.0.1:81 \
  -e NPM_EMAIL= \
  -e NPM_PASSWORD= \
  ghcr.io/hakuzero4/mcp-server
```

## Agent 用法

用户说「帮我创建一个服务 `<ip>` `<port>` 端口，启用自定义证书，域名为 `app.home.com`」时，调用 `nginxproxy_create_service`：

```json
{
  "domain": "app.home.com",
  "ip": "10.0.0.10",
  "port": 8080,
  "use_custom_certificate": true
}
```

工具会查找已上传的自定义 / 通配符证书并强制 HTTPS。

## 测试

```bash
uv run --package nginxproxy pytest nginxproxy/tests
```
