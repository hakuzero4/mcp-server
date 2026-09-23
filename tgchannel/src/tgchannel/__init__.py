"""Public Telegram channel FastMCP server."""

from tgchannel.constants import NAMESPACE
from tgchannel.server import create_server, main, mcp

__all__ = ["NAMESPACE", "create_server", "main", "mcp"]
