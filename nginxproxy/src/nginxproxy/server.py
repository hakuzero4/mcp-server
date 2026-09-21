"""FastMCP server wrapping Nginx Proxy Manager."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.server.transforms import Namespace

from nginxproxy.client import NpmClient
from nginxproxy.constants import INSTRUCTIONS, NAMESPACE
from nginxproxy.settings import Settings
from nginxproxy.tools import register_all


def create_server(
    *,
    namespaced: bool = True,
    settings: Settings | None = None,
    client: NpmClient | None = None,
) -> FastMCP:
    """Build the Nginx Proxy Manager MCP server.

    Args:
        namespaced: Prefix tools/prompts with `nginxproxy_` and resources with
            `npm://nginxproxy/...`. Disable this when a parent server will call
            `mount(..., namespace="nginxproxy")`.
        settings: Optional connection settings. Defaults to `NPM_*` env vars.
        client: Optional pre-built API client (used by tests).
    """

    @lifespan
    async def npm_lifespan(_server: FastMCP) -> AsyncIterator[dict[str, NpmClient]]:
        owned = client is None
        npm_client = client if client is not None else NpmClient(settings or Settings())
        try:
            yield {"npm": npm_client}
        finally:
            if owned:
                await npm_client.aclose()

    mcp = FastMCP(
        name=NAMESPACE,
        instructions=INSTRUCTIONS,
        lifespan=npm_lifespan,
    )
    register_all(mcp)
    if namespaced:
        mcp.add_transform(Namespace(NAMESPACE))
    return mcp


mcp = create_server()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
