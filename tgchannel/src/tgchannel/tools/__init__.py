"""Register tgchannel MCP tools."""

from __future__ import annotations

from fastmcp import FastMCP

from tgchannel.tools import channels


def register_all(mcp: FastMCP) -> None:
    channels.register(mcp)
