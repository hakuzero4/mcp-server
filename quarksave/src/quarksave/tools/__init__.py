"""Register quarksave MCP tools, resources, and prompts."""

from __future__ import annotations

from fastmcp import FastMCP

from quarksave.tools import transfer


def register_all(mcp: FastMCP) -> None:
    transfer.register(mcp)
