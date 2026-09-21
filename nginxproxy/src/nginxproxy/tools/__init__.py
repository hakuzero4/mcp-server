"""Register all nginxproxy MCP tools, resources, and prompts."""

from __future__ import annotations

from fastmcp import FastMCP

from nginxproxy.tools import (
    access_lists,
    admin,
    certificates,
    dead_hosts,
    proxy_hosts,
    redirection_hosts,
    streams,
)


def register_all(mcp: FastMCP) -> None:
    proxy_hosts.register(mcp)
    certificates.register(mcp)
    redirection_hosts.register(mcp)
    dead_hosts.register(mcp)
    streams.register(mcp)
    access_lists.register(mcp)
    admin.register(mcp)
