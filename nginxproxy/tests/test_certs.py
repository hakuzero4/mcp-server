from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from nginxproxy.certs import domain_matches, resolve_custom_certificate

HOME_CERT = {
    "id": 2,
    "provider": "other",
    "nice_name": "home.com",
    "domain_names": ["*.home.com"],
}


def test_wildcard_matches_one_label() -> None:
    assert domain_matches("*.home.com", "app.home.com")
    assert domain_matches("*.home.com", "APP.HOME.COM")
    assert not domain_matches("*.home.com", "home.com")
    assert not domain_matches("*.home.com", "a.b.home.com")
    assert not domain_matches("*.home.com", "evil.home.com.example")


def test_resolve_picks_covering_custom_cert() -> None:
    cert = resolve_custom_certificate([HOME_CERT], "app.home.com")
    assert cert["id"] == 2


def test_resolve_by_name() -> None:
    cert = resolve_custom_certificate(
        [HOME_CERT], "other.example", certificate_name="home.com"
    )
    assert cert["id"] == 2


def test_resolve_missing_custom_certs() -> None:
    with pytest.raises(ToolError, match="No custom"):
        resolve_custom_certificate([], "app.home.com")
