"""Redirection host tools."""

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
PATH = "/nginx/redirection-hosts"


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def list_redirection_hosts(
        ctx: Context,
        query: str | None = None,
        expand: list[str] | str | None = None,
    ) -> Any:
        """List HTTP redirection hosts.

        Args:
            query: Optional domain-name search filter.
            expand: Relations to include: owner, certificate.
        """
        return await call(
            npm(ctx).get(PATH, params={"query": query, "expand": expand_param(expand)})
        )

    @mcp.tool(annotations=READ)
    async def get_redirection_host(host_id: int, ctx: Context) -> Any:
        """Get one redirection host by id."""
        return await call(npm(ctx).get(f"{PATH}/{host_id}"))

    @mcp.tool(annotations=WRITE)
    async def create_redirection_host(
        ctx: Context,
        domain_names: list[str],
        forward_domain_name: str,
        forward_scheme: Literal["auto", "http", "https"] = "auto",
        forward_http_code: int = 301,
        preserve_path: bool = True,
        certificate_id: int | Literal["new"] = 0,
        ssl_forced: bool = False,
        http2_support: bool = False,
        hsts_enabled: bool = False,
        hsts_subdomains: bool = False,
        block_exploits: bool = True,
        advanced_config: str = "",
        letsencrypt_email: str | None = None,
    ) -> Any:
        """Create a host that redirects one or more domains to another domain.

        Args:
            domain_names: Source hostnames.
            forward_domain_name: Redirect target hostname.
            forward_scheme: auto keeps the incoming scheme.
            forward_http_code: Redirect status, typically 301 or 302.
            preserve_path: Keep the original path on the target URL.
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
                "forward_domain_name": forward_domain_name,
                "forward_scheme": forward_scheme,
                "forward_http_code": forward_http_code,
                "preserve_path": preserve_path,
                "certificate_id": certificate_id,
                "ssl_forced": ssl_forced,
                "http2_support": http2_support,
                "hsts_enabled": hsts_enabled,
                "hsts_subdomains": hsts_subdomains,
                "block_exploits": block_exploits,
                "advanced_config": advanced_config,
                "meta": meta,
            }
        )
        return await call(npm(ctx).post(PATH, json=payload))

    @mcp.tool(annotations=WRITE)
    async def update_redirection_host(
        host_id: int,
        ctx: Context,
        domain_names: list[str] | None = None,
        forward_domain_name: str | None = None,
        forward_scheme: Literal["auto", "http", "https"] | None = None,
        forward_http_code: int | None = None,
        preserve_path: bool | None = None,
        certificate_id: int | Literal["new"] | None = None,
        ssl_forced: bool | None = None,
        http2_support: bool | None = None,
        hsts_enabled: bool | None = None,
        hsts_subdomains: bool | None = None,
        block_exploits: bool | None = None,
        advanced_config: str | None = None,
    ) -> Any:
        """Update fields on an existing redirection host. Omitted fields are left unchanged."""
        payload = compact(
            {
                "domain_names": domain_names,
                "forward_domain_name": forward_domain_name,
                "forward_scheme": forward_scheme,
                "forward_http_code": forward_http_code,
                "preserve_path": preserve_path,
                "certificate_id": certificate_id,
                "ssl_forced": ssl_forced,
                "http2_support": http2_support,
                "hsts_enabled": hsts_enabled,
                "hsts_subdomains": hsts_subdomains,
                "block_exploits": block_exploits,
                "advanced_config": advanced_config,
            }
        )
        return await call(npm(ctx).put(f"{PATH}/{host_id}", json=payload))

    @mcp.tool(annotations=DESTRUCTIVE)
    async def delete_redirection_host(host_id: int, ctx: Context) -> Any:
        """Delete a redirection host by id."""
        return await call(npm(ctx).delete(f"{PATH}/{host_id}"))

    @mcp.tool(annotations=WRITE)
    async def enable_redirection_host(host_id: int, ctx: Context) -> Any:
        """Enable a disabled redirection host."""
        return await call(npm(ctx).post(f"{PATH}/{host_id}/enable"))

    @mcp.tool(annotations=WRITE)
    async def disable_redirection_host(host_id: int, ctx: Context) -> Any:
        """Disable a redirection host without deleting it."""
        return await call(npm(ctx).post(f"{PATH}/{host_id}/disable"))
