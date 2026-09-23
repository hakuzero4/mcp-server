"""FastMCP server that reads public Telegram channels."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.server.transforms import Namespace

from tgchannel.archive import Archive
from tgchannel.client import TgClient
from tgchannel.constants import INSTRUCTIONS, NAMESPACE
from tgchannel.settings import Settings
from tgchannel.tools import register_all


def create_server(
    *,
    namespaced: bool = True,
    settings: Settings | None = None,
    client: TgClient | None = None,
    archive: Archive | None = None,
) -> FastMCP:
    """Build the public-channel MCP server.

    Args:
        namespaced: Prefix tools with `tgchannel_`. Disable this when a parent
            server will call `mount(..., namespace="tgchannel")`.
        settings: Optional credentials. Defaults to `TG_*` env vars.
        client: Optional pre-built client (used by tests). It is not connected here.
        archive: Optional pre-built archive (used by tests). It is not opened here.
    """

    @lifespan
    async def tg_lifespan(_server: FastMCP) -> AsyncIterator[dict[str, TgClient | Archive]]:
        chosen = settings
        if chosen is None and (client is None or archive is None):
            chosen = Settings()
        owned_client = client is None
        tg_client = client if client is not None else TgClient(chosen or Settings())
        owned_archive = archive is None
        database = archive if archive is not None else Archive((chosen or Settings()).store_path)
        try:
            yield {"tg": tg_client, "archive": database}
        finally:
            if owned_archive:
                database.close()
            if owned_client:
                await tg_client.aclose()

    mcp = FastMCP(
        name=NAMESPACE,
        instructions=INSTRUCTIONS,
        lifespan=tg_lifespan,
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
