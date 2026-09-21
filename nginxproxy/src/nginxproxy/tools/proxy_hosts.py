"""Proxy host tools."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from fastmcp.exceptions import ToolError

from nginxproxy.certs import resolve_custom_certificate, summarize_cert
from nginxproxy.deps import call, npm
from nginxproxy.models import ProxyLocation, compact, expand_param

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, openWorldHint=True, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    openWorldHint=True,
    idempotentHint=True,
)
PATH = "/nginx/proxy-hosts"


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def list_proxy_hosts(
        ctx: Context,
        query: str | None = None,
        expand: list[str] | str | None = None,
    ) -> Any:
        """List reverse-proxy hosts in Nginx Proxy Manager.

        Args:
            query: Optional domain-name search filter.
            expand: Relations to include: owner, certificate, access_list.
        """
        return await call(
            npm(ctx).get(PATH, params={"query": query, "expand": expand_param(expand)})
        )

    @mcp.tool(annotations=READ)
    async def get_proxy_host(host_id: int, ctx: Context) -> Any:
        """Get one proxy host by id."""
        return await call(npm(ctx).get(f"{PATH}/{host_id}"))

    @mcp.tool(annotations=WRITE)
    async def create_service(
        ctx: Context,
        domain: str,
        ip: str,
        port: int,
        use_custom_certificate: bool = True,
        certificate_id: int | None = None,
        certificate_name: str | None = None,
        forward_scheme: Literal["http", "https"] = "http",
        force_ssl: bool = True,
        websocket: bool = False,
        block_exploits: bool = True,
    ) -> dict[str, Any]:
        """Create a reverse-proxy service from a domain, IP, and port.

        Use this when the user says things like:
        "帮我创建一个服务 10.0.0.10 8080 端口，启用自定义证书，域名为 app.home.com"

        Looks up an already-uploaded custom certificate (not Let's Encrypt),
        attaches it, and forces HTTPS. Existing hosts with the same domain are rejected.

        Args:
            domain: Public hostname, e.g. app.home.com.
            ip: Upstream IP or hostname.
            port: Upstream port.
            use_custom_certificate: Attach an uploaded custom/wildcard cert.
            certificate_id: Optional cert id. Omit to auto-pick a covering custom cert.
            certificate_name: Optional cert nice_name, e.g. home.com.
            forward_scheme: Protocol used to reach the upstream.
            force_ssl: Redirect HTTP to HTTPS once a certificate is attached.
            websocket: Allow WebSocket upgrades.
            block_exploits: Block common exploits.
        """
        domain = domain.strip()
        ip = ip.strip()
        existing = await call(npm(ctx).get(PATH, params={"query": domain}))
        if isinstance(existing, list):
            for host in existing:
                names = [str(name).lower() for name in (host.get("domain_names") or [])]
                if domain.lower() in names:
                    raise ToolError(
                        f"Domain {domain} already exists as proxy host id={host.get('id')} "
                        f"({host.get('forward_host')}:{host.get('forward_port')}). "
                        "Use update_proxy_host or delete_proxy_host first."
                    )

        cert: dict[str, Any] | None = None
        chosen_cert_id: int | Literal["new"] = 0
        ssl_forced = False
        if use_custom_certificate:
            certs = await call(npm(ctx).get("/nginx/certificates"))
            if not isinstance(certs, list):
                raise ToolError("Could not list certificates.")
            cert = resolve_custom_certificate(
                certs,
                domain,
                certificate_id=certificate_id,
                certificate_name=certificate_name,
            )
            chosen_cert_id = int(cert["id"])
            ssl_forced = force_ssl

        payload = compact(
            {
                "domain_names": [domain],
                "forward_host": ip,
                "forward_port": port,
                "forward_scheme": forward_scheme,
                "certificate_id": chosen_cert_id,
                "ssl_forced": ssl_forced,
                "http2_support": False,
                "block_exploits": block_exploits,
                "allow_websocket_upgrade": websocket,
                "access_list_id": 0,
                "advanced_config": "",
                "locations": [],
                "enabled": True,
                "meta": {},
            }
        )
        created = await call(npm(ctx).post(PATH, json=payload))
        return {
            "id": created.get("id") if isinstance(created, dict) else None,
            "domain": domain,
            "upstream": f"{forward_scheme}://{ip}:{port}",
            "ssl_forced": ssl_forced,
            "certificate": summarize_cert(cert) if cert else None,
            "host": created,
        }

    @mcp.tool(annotations=WRITE)
    async def create_proxy_host(
        ctx: Context,
        domain_names: list[str],
        forward_host: str,
        forward_port: int,
        forward_scheme: Literal["http", "https"] = "http",
        certificate_id: int | Literal["new"] = 0,
        ssl_forced: bool = False,
        http2_support: bool = False,
        hsts_enabled: bool = False,
        hsts_subdomains: bool = False,
        block_exploits: bool = True,
        caching_enabled: bool = False,
        allow_websocket_upgrade: bool = False,
        access_list_id: int = 0,
        advanced_config: str = "",
        locations: list[ProxyLocation] | None = None,
        letsencrypt_email: str | None = None,
        enabled: bool = True,
    ) -> Any:
        """Create a reverse-proxy host with explicit NPM fields.

        For "IP + port + 自定义证书 + 域名" requests, use create_service instead.

        Args:
            domain_names: Public hostnames, e.g. ["app.example.com"].
            forward_host: Upstream hostname or IP.
            forward_port: Upstream port.
            forward_scheme: Protocol used to reach the upstream.
            certificate_id: Existing certificate id, 0 for none, or "new" to issue Let's Encrypt.
            ssl_forced: Redirect HTTP to HTTPS.
            http2_support: Enable HTTP/2 when TLS is on.
            hsts_enabled: Send HSTS header.
            hsts_subdomains: Include subdomains in HSTS.
            block_exploits: Block common exploits.
            caching_enabled: Enable asset caching.
            allow_websocket_upgrade: Allow WebSocket upgrades.
            access_list_id: Access list id, or 0 for public.
            advanced_config: Extra nginx directives for the server block.
            locations: Extra path-based upstreams.
            letsencrypt_email: Email used when certificate_id is "new".
            enabled: Whether the host is enabled after creation.
        """
        meta: dict[str, Any] = {}
        if certificate_id == "new":
            meta["letsencrypt_agree"] = True
            if letsencrypt_email:
                meta["letsencrypt_email"] = letsencrypt_email
        payload = compact(
            {
                "domain_names": domain_names,
                "forward_host": forward_host,
                "forward_port": forward_port,
                "forward_scheme": forward_scheme,
                "certificate_id": certificate_id,
                "ssl_forced": ssl_forced,
                "http2_support": http2_support,
                "hsts_enabled": hsts_enabled,
                "hsts_subdomains": hsts_subdomains,
                "block_exploits": block_exploits,
                "caching_enabled": caching_enabled,
                "allow_websocket_upgrade": allow_websocket_upgrade,
                "access_list_id": access_list_id,
                "advanced_config": advanced_config,
                "locations": [loc.model_dump(exclude_none=True) for loc in locations]
                if locations
                else [],
                "enabled": enabled,
                "meta": meta,
            }
        )
        return await call(npm(ctx).post(PATH, json=payload))

    @mcp.tool(annotations=WRITE)
    async def update_proxy_host(
        host_id: int,
        ctx: Context,
        domain_names: list[str] | None = None,
        forward_host: str | None = None,
        forward_port: int | None = None,
        forward_scheme: Literal["http", "https"] | None = None,
        certificate_id: int | Literal["new"] | None = None,
        ssl_forced: bool | None = None,
        http2_support: bool | None = None,
        hsts_enabled: bool | None = None,
        hsts_subdomains: bool | None = None,
        block_exploits: bool | None = None,
        caching_enabled: bool | None = None,
        allow_websocket_upgrade: bool | None = None,
        access_list_id: int | None = None,
        advanced_config: str | None = None,
        locations: list[ProxyLocation] | None = None,
        enabled: bool | None = None,
    ) -> Any:
        """Update fields on an existing proxy host. Omitted fields are left unchanged."""
        payload = compact(
            {
                "domain_names": domain_names,
                "forward_host": forward_host,
                "forward_port": forward_port,
                "forward_scheme": forward_scheme,
                "certificate_id": certificate_id,
                "ssl_forced": ssl_forced,
                "http2_support": http2_support,
                "hsts_enabled": hsts_enabled,
                "hsts_subdomains": hsts_subdomains,
                "block_exploits": block_exploits,
                "caching_enabled": caching_enabled,
                "allow_websocket_upgrade": allow_websocket_upgrade,
                "access_list_id": access_list_id,
                "advanced_config": advanced_config,
                "locations": [loc.model_dump(exclude_none=True) for loc in locations]
                if locations is not None
                else None,
                "enabled": enabled,
            }
        )
        return await call(npm(ctx).put(f"{PATH}/{host_id}", json=payload))

    @mcp.tool(annotations=DESTRUCTIVE)
    async def delete_proxy_host(host_id: int, ctx: Context) -> Any:
        """Delete a proxy host by id."""
        return await call(npm(ctx).delete(f"{PATH}/{host_id}"))

    @mcp.tool(annotations=WRITE)
    async def enable_proxy_host(host_id: int, ctx: Context) -> Any:
        """Enable a disabled proxy host."""
        return await call(npm(ctx).post(f"{PATH}/{host_id}/enable"))

    @mcp.tool(annotations=WRITE)
    async def disable_proxy_host(host_id: int, ctx: Context) -> Any:
        """Disable a proxy host without deleting it."""
        return await call(npm(ctx).post(f"{PATH}/{host_id}/disable"))
