"""Resolve uploaded custom certificates for a domain."""

from __future__ import annotations

from typing import Any

from fastmcp.exceptions import ToolError


def normalize_domain(value: str) -> str:
    return value.strip().lower().rstrip(".")


def domain_matches(pattern: str, domain: str) -> bool:
    """Return True if an NPM certificate SAN covers `domain`.

    `*.home.com` matches `app.home.com` and not `home.com` or `a.b.home.com`.
    """
    pattern = normalize_domain(pattern)
    domain = normalize_domain(domain)
    if pattern.startswith("*."):
        parent = pattern[2:]
        if not domain.endswith("." + parent):
            return False
        prefix = domain[: -(len(parent) + 1)]
        return bool(prefix) and "." not in prefix
    return domain == pattern


def cert_covers_domain(cert: dict[str, Any], domain: str) -> bool:
    names = cert.get("domain_names") or []
    return any(domain_matches(str(name), domain) for name in names)


def summarize_cert(cert: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": cert.get("id"),
        "provider": cert.get("provider"),
        "nice_name": cert.get("nice_name"),
        "domain_names": cert.get("domain_names") or [],
        "expires_on": cert.get("expires_on"),
    }


def resolve_custom_certificate(
    certs: list[dict[str, Any]],
    domain: str,
    *,
    certificate_id: int | None = None,
    certificate_name: str | None = None,
) -> dict[str, Any]:
    """Pick an uploaded custom certificate for this domain."""
    if certificate_id is not None:
        for cert in certs:
            if cert.get("id") == certificate_id:
                return cert
        raise ToolError(f"No certificate with id {certificate_id}.")

    if certificate_name:
        needle = certificate_name.strip().lower()
        matches = [
            cert
            for cert in certs
            if str(cert.get("nice_name") or "").strip().lower() == needle
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ToolError(f"No certificate named {certificate_name!r}.")
        raise ToolError(
            f"Multiple certificates named {certificate_name!r}: "
            + ", ".join(str(cert.get("id")) for cert in matches)
        )

    custom = [cert for cert in certs if cert.get("provider") == "other"]
    covering = [cert for cert in custom if cert_covers_domain(cert, domain)]
    if len(covering) == 1:
        return covering[0]
    if len(covering) > 1:
        raise ToolError(
            "Multiple custom certificates cover "
            f"{domain}: "
            + ", ".join(
                f"{cert.get('id')} ({cert.get('nice_name')})" for cert in covering
            )
            + ". Pass certificate_id or certificate_name."
        )
    if len(custom) == 1:
        return custom[0]
    if not custom:
        raise ToolError(
            "No custom (uploaded) certificates exist. "
            "Upload one with create_custom_certificate, or pass certificate_id."
        )
    raise ToolError(
        f"No custom certificate covers {domain}. Available: "
        + ", ".join(
            f"{cert.get('id')} {cert.get('nice_name')} {cert.get('domain_names')}"
            for cert in custom
        )
        + ". Pass certificate_id or certificate_name."
    )
