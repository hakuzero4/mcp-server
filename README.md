# mcp-server

用 [uv](https://docs.astral.sh/uv/) 管理的 FastMCP 服务集合。每个服务一个目录，用 FastMCP `namespace` 避免工具重名。

镜像由 GitHub Actions 构建并推送到 GHCR：

`ghcr.io/hakuzero4/mcp-server`

| 目录 | Namespace | 说明 |
| --- | --- | --- |
| [`nginxproxy/`](nginxproxy/) | `nginxproxy` | [Nginx Proxy Manager](https://nginxproxymanager.com) API |
| [`quarksave/`](quarksave/) | `quarksave` | [quark-auto-save](https://github.com/Cp0204/quark-auto-save) 夸克转存 |

工具名、参数和资源见各服务的 README：[nginxproxy](nginxproxy/README.md)、[quarksave](quarksave/README.md)。

## 给 Agent

客户端只连 `http://<host>:8000/mcp`。用户只说一句话时：

| 用户说 | 调用 |
| --- | --- |
| 帮我创建一个服务 `10.0.0.10` 的 `8080` 端口，启用自定义证书，域名为 `app.home.com` | `nginxproxy_create_service` |
| 把 `https://pan.quark.cn/s/xxxx` 转存到我的夸克 | `quarksave_save`，只传 `shareurl` |

## 添加一个新的 MCP 服务

1. 在仓库根目录创建包（会自动加入 uv workspace）：

   ```bash
   uv init --package my-service
   ```

2. 实现 `my-service/src/my-service/server.py`，导出 `create_server()` 或 `mcp`，并用目录名做 namespace：

   ```python
   from fastmcp import FastMCP
   from fastmcp.server.transforms import Namespace

   def create_server(*, namespaced: bool = True) -> FastMCP:
       mcp = FastMCP("my-service")
       # 注册 tools / resources / prompts
       if namespaced:
           mcp.add_transform(Namespace("my-service"))
       return mcp

   mcp = create_server()
   ```

3. 安装依赖并锁定：

   ```bash
   uv add --package my-service fastmcp
   uv lock
   uv run --package my-service pytest
   ```

4. 提交推送。`run.py` 会扫描带 `src/<name>/server.py` 的目录，Dockerfile 会把新包打进同一张镜像，无需改 Dockerfile。

5. 推送后同一张镜像即可用。一个进程默认挂载全部服务（FastMCP `mount` + namespace）。

约定：

- 目录名 = 包名 = namespace
- 密钥只走环境变量或 `.env`（已 gitignore），不要写进代码或镜像
- 每个服务的 README 写该服务的环境变量和工具，示例用占位符

## 本地开发

```bash
uv sync --all-packages
uv run pytest
uv run python run.py --list
uv run python run.py all
```

`run.py` 默认 HTTP：`http://127.0.0.1:8000/mcp`，健康检查 `GET /health`。

stdio：

```bash
MCP_TRANSPORT=stdio uv run python run.py all
```

## Docker

复制 `.env.example` 为 `.env` 并填入配置，然后直接拉镜像启动（不在本地 build）：

```bash
cp .env.example .env
docker compose pull
docker compose up -d
```

MCP 地址：`http://<host>:8000/mcp`。镜像来自 `ghcr.io/hakuzero4/mcp-server:latest`。

拉镜像若出现 `download failed ... EOF`，等 Actions 编完后再 `docker compose pull`。本地已有镜像时 Compose 不会每次重拉。

私有包先登录：

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

stdio 模式：

```bash
docker run --rm -i \
  -e MCP_TRANSPORT=stdio \
  -e MCP_SERVER=all \
  -e NPM_URL=http://127.0.0.1:81 \
  -e NPM_EMAIL= \
  -e NPM_PASSWORD= \
  -e QAS_URL=http://127.0.0.1:5005 \
  -e QAS_USERNAME= \
  -e QAS_PASSWORD= \
  ghcr.io/hakuzero4/mcp-server
```

## `MCP_SERVER`：一个入口，按名字路由

FastMCP 可以在**同一个进程**里挂载多个子服务。客户端只连 `http://<host>:8000/mcp`，工具名用 namespace 区分：`nginxproxy_create_service`、`quarksave_save`。

| `MCP_SERVER` | 行为 |
| --- | --- |
| `all`（默认） | `mount` 仓库里每一个服务 |
| `nginxproxy` | 只跑这一个 |
| `nginxproxy,my-service` | 只挂载列出的几个 |

```bash
docker run --rm -p 8000:8000 -e MCP_SERVER=all ghcr.io/hakuzero4/mcp-server
```

这是工具级路由，不是 `/mcp/nginxproxy` 这种 URL 路径。一个 HTTP 端点，多个 namespace。

## GitHub 镜像

推送到 `main` / `master` 或打 `v*` tag 后，Actions 会：

1. 跑测试
2. 构建 `linux/amd64` 与 `linux/arm64`
3. 推送到 `ghcr.io/hakuzero4/mcp-server`

拉取：

```bash
docker pull ghcr.io/hakuzero4/mcp-server:latest
```

私有包需要先登录：

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

仓库 Settings → Actions → General 需允许 workflow 写入 packages。首次推送后可在 GitHub Packages 把镜像设为 public。
