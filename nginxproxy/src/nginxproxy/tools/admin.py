"""Status, users, settings, reports, audit log, resources, and prompts."""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from nginxproxy.deps import call, npm
from nginxproxy.models import compact, expand_param

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, openWorldHint=True, idempotentHint=False)


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def get_status(ctx: Context) -> Any:
        """Return Nginx Proxy Manager API status from GET /api/."""
        return await call(npm(ctx).get("/"))

    @mcp.tool(annotations=READ)
    async def get_hosts_report(ctx: Context) -> Any:
        """Return counts of proxy, redirection, stream, and 404 hosts."""
        return await call(npm(ctx).get("/reports/hosts"))

    @mcp.tool(annotations=READ)
    async def get_audit_log(ctx: Context, expand: list[str] | str | None = None) -> Any:
        """Return the Nginx Proxy Manager audit log.

        Args:
            expand: Relations to include, typically user.
        """
        return await call(npm(ctx).get("/audit-log", params={"expand": expand_param(expand)}))

    @mcp.tool(annotations=READ)
    async def list_users(
        ctx: Context,
        query: str | None = None,
        expand: list[str] | str | None = None,
    ) -> Any:
        """List Nginx Proxy Manager users.

        Args:
            query: Optional search filter.
            expand: Relations to include.
        """
        return await call(
            npm(ctx).get("/users", params={"query": query, "expand": expand_param(expand)})
        )

    @mcp.tool(annotations=READ)
    async def get_user(user_id: int, ctx: Context) -> Any:
        """Get one user by id."""
        return await call(npm(ctx).get(f"/users/{user_id}"))

    @mcp.tool(annotations=READ)
    async def list_settings(ctx: Context) -> Any:
        """List application settings."""
        return await call(npm(ctx).get("/settings"))

    @mcp.tool(annotations=READ)
    async def get_setting(setting_id: str, ctx: Context) -> Any:
        """Get one setting by id, e.g. default-site."""
        return await call(npm(ctx).get(f"/settings/{setting_id}"))

    @mcp.tool(annotations=WRITE)
    async def update_setting(setting_id: str, value: Any, ctx: Context) -> Any:
        """Update a setting.

        Args:
            setting_id: Setting id, e.g. default-site.
            value: New value. Shape depends on the setting.
        """
        payload = value if isinstance(value, dict) else compact({"value": value})
        return await call(npm(ctx).put(f"/settings/{setting_id}", json=payload))

    @mcp.resource("npm://status", mime_type="application/json")
    async def status_resource(ctx: Context) -> Any:
        """Current Nginx Proxy Manager API status."""
        return await call(npm(ctx).get("/"))

    @mcp.resource("npm://proxy-hosts", mime_type="application/json")
    async def proxy_hosts_resource(ctx: Context) -> Any:
        """All proxy hosts."""
        return await call(npm(ctx).get("/nginx/proxy-hosts"))

    @mcp.resource("npm://proxy-hosts/{host_id}", mime_type="application/json")
    async def proxy_host_resource(host_id: str, ctx: Context) -> Any:
        """One proxy host by id."""
        return await call(npm(ctx).get(f"/nginx/proxy-hosts/{host_id}"))

    @mcp.resource("npm://certificates", mime_type="application/json")
    async def certificates_resource(ctx: Context) -> Any:
        """All certificates."""
        return await call(npm(ctx).get("/nginx/certificates"))

    @mcp.resource("npm://report", mime_type="application/json")
    async def report_resource(ctx: Context) -> Any:
        """Host counts report."""
        return await call(npm(ctx).get("/reports/hosts"))

    @mcp.prompt
    def create_https_proxy_guide(domain: str, forward_host: str, forward_port: int) -> str:
        """Guide for exposing a backend with a custom certificate through Nginx Proxy Manager."""
        return (
            f"Expose `{domain}` to `{forward_host}:{forward_port}` with the uploaded custom certificate.\n\n"
            "Call `nginxproxy_create_service` with:\n"
            f"  - domain: {domain}\n"
            f"  - ip: {forward_host}\n"
            f"  - port: {forward_port}\n"
            "  - use_custom_certificate: true\n\n"
            "That picks the custom/wildcard cert (for example *.home.com), attaches it, and forces HTTPS.\n"
            "If the domain already exists, tell the user the existing host id instead of creating a duplicate.\n"
        )
