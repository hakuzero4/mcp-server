"""Register tgchannel MCP tools."""

from __future__ import annotations

from fastmcp import FastMCP

from tgchannel.tools import archive, channels


def register_all(mcp: FastMCP) -> None:
    channels.register(mcp)
    archive.register(mcp)
