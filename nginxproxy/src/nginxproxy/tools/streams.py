"""TCP/UDP stream tools."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from nginxproxy.deps import call, npm
from nginxproxy.models import compact, expand_param

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, openWorldHint=True, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    openWorldHint=True,
    idempotentHint=True,
)
PATH = "/nginx/streams"


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def list_streams(
        ctx: Context,
        query: str | None = None,
        expand: list[str] | str | None = None,
    ) -> Any:
        """List TCP/UDP stream forwards.

        Args:
            query: Optional search filter.
            expand: Relations to include, typically owner.
        """
        return await call(
            npm(ctx).get(PATH, params={"query": query, "expand": expand_param(expand)})
        )

    @mcp.tool(annotations=READ)
    async def get_stream(stream_id: int, ctx: Context) -> Any:
        """Get one stream by id."""
        return await call(npm(ctx).get(f"{PATH}/{stream_id}"))

    @mcp.tool(annotations=WRITE)
    async def create_stream(
        ctx: Context,
        incoming_port: int,
        forwarding_host: str,
        forwarding_port: int,
        tcp_forwarding: bool = True,
        udp_forwarding: bool = False,
        certificate_id: int = 0,
    ) -> Any:
        """Create a TCP and/or UDP port forward.

        Args:
            incoming_port: Port Nginx Proxy Manager listens on.
            forwarding_host: Upstream hostname or IP.
            forwarding_port: Upstream port.
            tcp_forwarding: Forward TCP.
            udp_forwarding: Forward UDP.
            certificate_id: Optional certificate for TLS streams, 0 for none.
        """
        payload = compact(
            {
                "incoming_port": incoming_port,
                "forwarding_host": forwarding_host,
                "forwarding_port": forwarding_port,
                "tcp_forwarding": tcp_forwarding,
                "udp_forwarding": udp_forwarding,
                "certificate_id": certificate_id,
            }
        )
        return await call(npm(ctx).post(PATH, json=payload))

    @mcp.tool(annotations=WRITE)
    async def update_stream(
        stream_id: int,
        ctx: Context,
        incoming_port: int | None = None,
        forwarding_host: str | None = None,
        forwarding_port: int | None = None,
        tcp_forwarding: bool | None = None,
        udp_forwarding: bool | None = None,
        certificate_id: int | None = None,
    ) -> Any:
        """Update fields on an existing stream. Omitted fields are left unchanged."""
        payload = compact(
            {
                "incoming_port": incoming_port,
                "forwarding_host": forwarding_host,
                "forwarding_port": forwarding_port,
                "tcp_forwarding": tcp_forwarding,
                "udp_forwarding": udp_forwarding,
                "certificate_id": certificate_id,
            }
        )
        return await call(npm(ctx).put(f"{PATH}/{stream_id}", json=payload))

    @mcp.tool(annotations=DESTRUCTIVE)
    async def delete_stream(stream_id: int, ctx: Context) -> Any:
        """Delete a stream by id."""
        return await call(npm(ctx).delete(f"{PATH}/{stream_id}"))

    @mcp.tool(annotations=WRITE)
    async def enable_stream(stream_id: int, ctx: Context) -> Any:
        """Enable a disabled stream."""
        return await call(npm(ctx).post(f"{PATH}/{stream_id}/enable"))

    @mcp.tool(annotations=WRITE)
    async def disable_stream(stream_id: int, ctx: Context) -> Any:
        """Disable a stream without deleting it."""
        return await call(npm(ctx).post(f"{PATH}/{stream_id}/disable"))
