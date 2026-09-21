"""Certificate tools."""

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
PATH = "/nginx/certificates"


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ)
    async def list_certificates(
        ctx: Context,
        query: str | None = None,
        expand: list[str] | str | None = None,
    ) -> Any:
        """List TLS certificates managed by Nginx Proxy Manager.

        Args:
            query: Optional domain-name search filter.
            expand: Relations to include, typically owner.
        """
        return await call(
            npm(ctx).get(PATH, params={"query": query, "expand": expand_param(expand)})
        )

    @mcp.tool(annotations=READ)
    async def get_certificate(cert_id: int, ctx: Context) -> Any:
        """Get one certificate by id."""
        return await call(npm(ctx).get(f"{PATH}/{cert_id}"))

    @mcp.tool(annotations=READ)
    async def list_dns_providers(ctx: Context) -> Any:
        """List DNS providers that can be used for Let's Encrypt DNS-01 challenges."""
        return await call(npm(ctx).get(f"{PATH}/dns-providers"))

    @mcp.tool(annotations=READ)
    async def test_certificate_http(domain_names: list[str], ctx: Context) -> Any:
        """Test whether domains are reachable over HTTP for Let's Encrypt HTTP-01."""
        return await call(npm(ctx).post(f"{PATH}/test-http", json={"domains": domain_names}))

    @mcp.tool(annotations=WRITE)
    async def create_letsencrypt_certificate(
        ctx: Context,
        domain_names: list[str],
        letsencrypt_email: str,
        dns_challenge: bool = False,
        dns_provider: str | None = None,
        dns_provider_credentials: str | None = None,
        propagation_seconds: int | None = None,
        key_type: Literal["ecdsa", "rsa"] = "ecdsa",
    ) -> Any:
        """Issue a Let's Encrypt certificate.

        Args:
            domain_names: Names to include on the certificate. Wildcards need DNS-01.
            letsencrypt_email: Contact email for Let's Encrypt.
            dns_challenge: Use DNS-01 instead of HTTP-01.
            dns_provider: Provider id from list_dns_providers when using DNS-01.
            dns_provider_credentials: Provider credentials (INI-style string).
            propagation_seconds: Extra wait for DNS propagation.
            key_type: Certificate key type.
        """
        meta = compact(
            {
                "letsencrypt_email": letsencrypt_email,
                "letsencrypt_agree": True,
                "dns_challenge": dns_challenge,
                "dns_provider": dns_provider,
                "dns_provider_credentials": dns_provider_credentials,
                "propagation_seconds": propagation_seconds,
                "key_type": key_type,
            }
        )
        payload = {
            "provider": "letsencrypt",
            "domain_names": domain_names,
            "meta": meta,
        }
        return await call(npm(ctx).post(PATH, json=payload))

    @mcp.tool(annotations=WRITE)
    async def create_custom_certificate(
        ctx: Context,
        nice_name: str,
        certificate_pem: str,
        certificate_key_pem: str,
        intermediate_pem: str | None = None,
        domain_names: list[str] | None = None,
    ) -> Any:
        """Create a custom certificate and upload PEM material.

        Args:
            nice_name: Display name in Nginx Proxy Manager.
            certificate_pem: Server certificate PEM.
            certificate_key_pem: Private key PEM.
            intermediate_pem: Optional intermediate/chain PEM.
            domain_names: Optional domain list stored on the certificate record.
        """
        created = await call(
            npm(ctx).post(
                PATH,
                json=compact(
                    {
                        "provider": "other",
                        "nice_name": nice_name,
                        "domain_names": domain_names,
                    }
                ),
            )
        )
        cert_id = created.get("id") if isinstance(created, dict) else None
        if cert_id is None:
            return created
        files: dict[str, tuple[str, str, str]] = {
            "certificate": ("cert.pem", certificate_pem, "application/x-pem-file"),
            "certificate_key": ("key.pem", certificate_key_pem, "application/x-pem-file"),
        }
        if intermediate_pem:
            files["intermediate_certificate"] = (
                "chain.pem",
                intermediate_pem,
                "application/x-pem-file",
            )
        uploaded = await call(npm(ctx).post(f"{PATH}/{cert_id}/upload", files=files))
        return {"certificate": created, "upload": uploaded}

    @mcp.tool(annotations=WRITE)
    async def renew_certificate(cert_id: int, ctx: Context) -> Any:
        """Renew a Let's Encrypt certificate."""
        return await call(npm(ctx).post(f"{PATH}/{cert_id}/renew"))

    @mcp.tool(annotations=DESTRUCTIVE)
    async def delete_certificate(cert_id: int, ctx: Context) -> Any:
        """Delete a certificate by id."""
        return await call(npm(ctx).delete(f"{PATH}/{cert_id}"))
