"""Launch workspace MCP servers, one name or a FastMCP-mounted gateway."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

ROOT = Path(__file__).resolve().parent
ALL = "all"


def discover_servers(root: Path = ROOT) -> dict[str, str]:
    """Map directory name → import path for `<name>.server`."""
    found: dict[str, str] = {}
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "src" / child.name / "server.py").is_file():
            found[child.name] = f"{child.name}.server"
    return found


def load_mcp(name: str, module_name: str, *, namespaced: bool = True):
    module = importlib.import_module(module_name)
    create = getattr(module, "create_server", None)
    if create is not None:
        return create(namespaced=namespaced)
    if not namespaced:
        raise SystemExit(
            f"{name}: export create_server(*, namespaced=True) so it can be mounted "
            "without a double namespace prefix"
        )
    mcp = getattr(module, "mcp", None)
    if mcp is None:
        raise SystemExit(f"{module_name} has neither create_server() nor mcp")
    return mcp


def parse_selection(raw: str, servers: dict[str, str]) -> list[str]:
    value = raw.strip()
    if not value or value == ALL:
        return list(servers)
    names = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [name for name in names if name not in servers]
    if unknown:
        available = ", ".join(servers) or "(none)"
        raise SystemExit(
            f"Unknown server {', '.join(unknown)}. Available: {available}, or {ALL}"
        )
    return names


def build_app(selection: str, servers: dict[str, str]) -> tuple[FastMCP, list[str]]:
    if not servers:
        raise SystemExit("No MCP servers found (expected <name>/src/<name>/server.py)")
    names = parse_selection(selection, servers)
    if len(names) == 1:
        return load_mcp(names[0], servers[names[0]], namespaced=True), names

    gateway = FastMCP(
        name="mcp-server",
        instructions=(
            "Gateway for multiple FastMCP servers. Tools are namespaced as "
            "<server>_<tool>, for example nginxproxy_create_service. "
            "Mounted: " + ", ".join(names) + "."
        ),
    )
    for name in names:
        child = load_mcp(name, servers[name], namespaced=False)
        gateway.mount(child, namespace=name)
    return gateway, names


def _selection(argv: list[str], servers: dict[str, str]) -> str:
    if "--list" in argv:
        print(ALL)
        for name in servers:
            print(name)
        raise SystemExit(0)
    env_name = os.environ.get("MCP_SERVER", "").strip()
    arg_name = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else ""
    return env_name or arg_name or ALL


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv if argv is None else argv)
    servers = discover_servers()
    selection = _selection(argv, servers)
    mcp, names = build_app(selection, servers)

    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "server": selection, "servers": names})

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
