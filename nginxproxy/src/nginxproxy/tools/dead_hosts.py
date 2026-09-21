"""404 / dead host tools."""

from __future__ import annotations

from typing import Any, Literal

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
PATH = "/nginx/dead-hosts"


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def list_dead_hosts(
        ctx: Context,
        query: str | None = None,
        expand: list[str] | str | None = None,
    ) -> Any:
        """List 404 (dead) hosts that catch unmatched domains.

        Args:
            query: Optional domain-name search filter.
            expand: Relations to include: owner, certificate.
        """
        return await call(
            npm(ctx).get(PATH, params={"query": query, "expand": expand_param(expand)})
        )

    @mcp.tool(annotations=READ)
    async def get_dead_host(host_id: int, ctx: Context) -> Any:
        """Get one 404 host by id."""
        return await call(npm(ctx).get(f"{PATH}/{host_id}"))

    @mcp.tool(annotations=WRITE)
    async def create_dead_host(
        ctx: Context,
        domain_names: list[str],
        certificate_id: int | Literal["new"] = 0,
        ssl_forced: bool = False,
        http2_support: bool = False,
        hsts_enabled: bool = False,
        hsts_subdomains: bool = False,
        advanced_config: str = "",
        letsencrypt_email: str | None = None,
    ) -> Any:
        """Create a 404 host for domains that should return not found.

        Args:
            domain_names: Hostnames that should serve 404.
            certificate_id: Existing certificate id, 0 for none, or "new" for Let's Encrypt.
            letsencrypt_email: Email used when certificate_id is "new".
        """
        meta: dict[str, Any] = {}
        if certificate_id == "new":
            meta["letsencrypt_agree"] = True
            if letsencrypt_email:
                meta["letsencrypt_email"] = letsencrypt_email
        payload = compact(
            {
                "domain_names": domain_names,
                "certificate_id": certificate_id,
                "ssl_forced": ssl_forced,
                "http2_support": http2_support,
                "hsts_enabled": hsts_enabled,
                "hsts_subdomains": hsts_subdomains,
                "advanced_config": advanced_config,
                "meta": meta,
            }
        )
        return await call(npm(ctx).post(PATH, json=payload))

    @mcp.tool(annotations=WRITE)
    async def update_dead_host(
        host_id: int,
        ctx: Context,
        domain_names: list[str] | None = None,
        certificate_id: int | Literal["new"] | None = None,
        ssl_forced: bool | None = None,
        http2_support: bool | None = None,
        hsts_enabled: bool | None = None,
        hsts_subdomains: bool | None = None,
        advanced_config: str | None = None,
    ) -> Any:
        """Update fields on an existing 404 host. Omitted fields are left unchanged."""
        payload = compact(
            {
                "domain_names": domain_names,
                "certificate_id": certificate_id,
                "ssl_forced": ssl_forced,
                "http2_support": http2_support,
                "hsts_enabled": hsts_enabled,
                "hsts_subdomains": hsts_subdomains,
                "advanced_config": advanced_config,
            }
        )
        return await call(npm(ctx).put(f"{PATH}/{host_id}", json=payload))

    @mcp.tool(annotations=DESTRUCTIVE)
    async def delete_dead_host(host_id: int, ctx: Context) -> Any:
        """Delete a 404 host by id."""
        return await call(npm(ctx).delete(f"{PATH}/{host_id}"))

    @mcp.tool(annotations=WRITE)
    async def enable_dead_host(host_id: int, ctx: Context) -> Any:
        """Enable a disabled 404 host."""
        return await call(npm(ctx).post(f"{PATH}/{host_id}/enable"))

    @mcp.tool(annotations=WRITE)
    async def disable_dead_host(host_id: int, ctx: Context) -> Any:
        """Disable a 404 host without deleting it."""
        return await call(npm(ctx).post(f"{PATH}/{host_id}/disable"))
