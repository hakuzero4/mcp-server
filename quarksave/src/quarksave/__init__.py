"""Quark-auto-save FastMCP server."""

from quarksave.constants import NAMESPACE
from quarksave.server import create_server, main, mcp

__all__ = ["NAMESPACE", "create_server", "main", "mcp"]
