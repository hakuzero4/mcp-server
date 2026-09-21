"""Launch a workspace MCP server by directory name."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

ROOT = Path(__file__).resolve().parent


def discover_servers(root: Path = ROOT) -> dict[str, str]:
    """Map directory name → import path for `<name>.server`."""
    found: dict[str, str] = {}
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "src" / child.name / "server.py").is_file():
            found[child.name] = f"{child.name}.server"
    return found


def load_mcp(name: str, module_name: str):
    module = importlib.import_module(module_name)
    if hasattr(module, "create_server"):
        return module.create_server()
    if hasattr(module, "mcp"):
        return module.mcp
    raise SystemExit(f"{module_name} has neither create_server() nor mcp")


def _server_name(argv: list[str], servers: dict[str, str]) -> str:
    if "--list" in argv:
        for name in servers:
            print(name)
        raise SystemExit(0)
    env_name = os.environ.get("MCP_SERVER", "").strip()
    arg_name = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else ""
    name = env_name or arg_name
    if not name and len(servers) == 1:
        return next(iter(servers))
    if not name:
        available = ", ".join(servers) or "(none)"
        raise SystemExit(f"Set MCP_SERVER or pass a server name. Available: {available}")
    if name not in servers:
        available = ", ".join(servers) or "(none)"
        raise SystemExit(f"Unknown server {name!r}. Available: {available}")
    return name


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv if argv is None else argv)
    servers = discover_servers()
    name = _server_name(argv, servers)
    mcp = load_mcp(name, servers[name])

    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "server": name})

    mcp.custom_route("/health", methods=["GET"])(health)

    transport = os.environ.get("MCP_TRANSPORT", "http").strip().lower()
    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    path = os.environ.get("MCP_PATH", "/mcp")
    mcp.run(transport="http", host=host, port=port, path=path)


if __name__ == "__main__":
    main()
