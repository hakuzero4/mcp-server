"""Nginx Proxy Manager FastMCP server."""

from nginxproxy.constants import NAMESPACE
from nginxproxy.server import create_server, main, mcp

__all__ = ["NAMESPACE", "create_server", "main", "mcp"]
