"""FastMCP server wrapping quark-auto-save transfers."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.server.transforms import Namespace

from quarksave.client import QasClient
from quarksave.constants import INSTRUCTIONS, NAMESPACE
from quarksave.settings import Settings
from quarksave.tools import register_all


def create_server(
    *,
    namespaced: bool = True,
    settings: Settings | None = None,
    client: QasClient | None = None,
) -> FastMCP:
    """Build the quark-auto-save MCP server.

    Args:
        namespaced: Prefix tools with `quarksave_`. Disable this when a parent
            server will call `mount(..., namespace="quarksave")`.
        settings: Optional connection settings. Defaults to `QAS_*` env vars.
        client: Optional pre-built API client (used by tests).
    """

    @lifespan
    async def qas_lifespan(_server: FastMCP) -> AsyncIterator[dict[str, QasClient]]:
        owned = client is None
        qas_client = client if client is not None else QasClient(settings or Settings())
        try:
            yield {"qas": qas_client}
        finally:
            if owned:
                await qas_client.aclose()

    mcp = FastMCP(
        name=NAMESPACE,
        instructions=INSTRUCTIONS,
        lifespan=qas_lifespan,
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
