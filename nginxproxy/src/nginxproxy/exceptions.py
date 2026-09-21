"""Errors raised by the Nginx Proxy Manager client."""

from __future__ import annotations

from typing import Any


class NpmApiError(Exception):
    """An Nginx Proxy Manager API call failed."""

    def __init__(self, status_code: int, message: str, body: Any = None) -> None:
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(f"NPM API {status_code}: {message}")
