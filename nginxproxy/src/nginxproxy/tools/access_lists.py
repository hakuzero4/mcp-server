"""Access list tools."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from nginxproxy.deps import call, npm
from nginxproxy.models import AccessClient, AccessItem, compact, expand_param

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, openWorldHint=True, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    openWorldHint=True,
    idempotentHint=True,
)
PATH = "/nginx/access-lists"


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def list_access_lists(
        ctx: Context,
        query: str | None = None,
        expand: list[str] | str | None = None,
    ) -> Any:
        """List access lists (basic auth and IP allow/deny).

        Args:
            query: Optional name search filter.
            expand: Relations to include, typically owner.
        """
        return await call(
            npm(ctx).get(PATH, params={"query": query, "expand": expand_param(expand)})
        )

    @mcp.tool(annotations=READ)
    async def get_access_list(list_id: int, ctx: Context) -> Any:
        """Get one access list by id."""
        return await call(npm(ctx).get(f"{PATH}/{list_id}"))

    @mcp.tool(annotations=WRITE)
    async def create_access_list(
        ctx: Context,
        name: str,
        satisfy_any: bool = False,
        pass_auth: bool = True,
        items: list[AccessItem] | None = None,
        clients: list[AccessClient] | None = None,
    ) -> Any:
        """Create an access list.

        Args:
            name: Display name.
            satisfy_any: If true, either auth or IP rule may match.
            pass_auth: Forward auth headers to the upstream.
            items: Basic-auth users.
            clients: IP allow/deny rules.
        """
        payload = compact(
            {
                "name": name,
                "satisfy_any": satisfy_any,
                "pass_auth": pass_auth,
                "items": [item.model_dump() for item in items] if items else [],
                "clients": [client.model_dump() for client in clients] if clients else [],
            }
        )
        return await call(npm(ctx).post(PATH, json=payload))

    @mcp.tool(annotations=WRITE)
    async def update_access_list(
        list_id: int,
        ctx: Context,
        name: str | None = None,
        satisfy_any: bool | None = None,
        pass_auth: bool | None = None,
        items: list[AccessItem] | None = None,
        clients: list[AccessClient] | None = None,
    ) -> Any:
        """Update an access list. Omitted fields are left unchanged."""
        payload = compact(
            {
                "name": name,
                "satisfy_any": satisfy_any,
                "pass_auth": pass_auth,
                "items": [item.model_dump() for item in items] if items is not None else None,
                "clients": [client.model_dump() for client in clients]
                if clients is not None
                else None,
            }
        )
        return await call(npm(ctx).put(f"{PATH}/{list_id}", json=payload))

    @mcp.tool(annotations=DESTRUCTIVE)
    async def delete_access_list(list_id: int, ctx: Context) -> Any:
        """Delete an access list by id."""
        return await call(npm(ctx).delete(f"{PATH}/{list_id}"))
