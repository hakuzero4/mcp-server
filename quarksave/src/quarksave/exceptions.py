"""Errors raised by the quark-auto-save client and task helpers."""

from __future__ import annotations

from typing import Any


class QasApiError(Exception):
    """A quark-auto-save API call failed."""

    def __init__(self, status_code: int, message: str, body: Any = None) -> None:
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(f"QAS API {status_code}: {message}")


class TaskError(Exception):
    """A transfer task is missing or its fields are invalid."""
