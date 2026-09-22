"""Async HTTP client for a quark-auto-save WebUI."""

from __future__ import annotations

from typing import Any

import httpx

from quarksave.exceptions import QasApiError
from quarksave.settings import Settings
from quarksave.tasks import parse_sse, summarize_task, trim_log


def _error_message(body: Any) -> str:
    if isinstance(body, dict):
        if body.get("message"):
            return str(body["message"])
        data = body.get("data")
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])
    if isinstance(body, str) and body.strip():
        return body.strip()
    return "request failed"


class QasClient:
    """Token-authenticated client for quark-auto-save.

    The WebUI expects the API token as a `token` query parameter. Cookie,
    notify config, and the API token itself are never returned to callers.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self._token = self.settings.token
        self._owned_http = http is None
        self._http = http or httpx.AsyncClient(
            base_url=self.settings.url,
            timeout=httpx.Timeout(self.settings.timeout),
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        if self._owned_http:
            await self._http.aclose()

    def _redact(self, text: str) -> str:
        if self._token and self._token in text:
            return text.replace(self._token, "***")
        return text

    async def _send(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> httpx.Response:
        if not self._token:
            raise QasApiError(401, "Missing QAS token. Set QAS_TOKEN.")
        query = {key: value for key, value in (params or {}).items() if value is not None}
        query["token"] = self._token
        try:
            response = await self._http.request(
                method,
                path,
                params=query,
                json=json,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise QasApiError(0, f"HTTP request failed: {self._redact(str(exc))}") from exc
        if response.is_redirect:
            raise QasApiError(
                response.status_code,
                "Quark-auto-save redirected the request. Check QAS_URL and QAS_TOKEN.",
            )
        return response

    def _parse_json(self, response: httpx.Response) -> Any:
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            raise QasApiError(
                response.status_code,
                "Quark-auto-save returned HTML. Check QAS_URL and QAS_TOKEN.",
            )
        if not response.content:
            if response.is_error:
                phrase = httpx.codes.get_reason_phrase(response.status_code) or "request failed"
                raise QasApiError(response.status_code, phrase)
            return {"success": True}
        try:
            body = response.json()
        except ValueError:
            text = self._redact(response.text.strip())
            if response.is_error:
                raise QasApiError(response.status_code, text or "request failed")
            raise QasApiError(response.status_code, "Expected JSON from quark-auto-save")
        message = self._redact(_error_message(body))
        failed = response.is_error or (isinstance(body, dict) and body.get("success") is False)
        if failed:
            raise QasApiError(response.status_code, message, body)
        if (
            isinstance(body, dict)
            and body.get("data") is None
            and isinstance(body.get("message"), str)
            and body["message"].lower().startswith("error")
        ):
            raise QasApiError(response.status_code, message, body)
        return body

    async def _json(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> Any:
        response = await self._send(method, path, json=json, params=params, timeout=timeout)
        return self._parse_json(response)

    async def _data(self) -> dict[str, Any]:
        body = await self._json("GET", "/data")
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise QasApiError(0, "Unexpected /data response")
        return data

    async def tasklist(self) -> list[dict[str, Any]]:
        tasks = (await self._data()).get("tasklist") or []
        if not isinstance(tasks, list):
            raise QasApiError(0, "tasklist is not a list")
        return tasks

    async def public_state(self) -> dict[str, Any]:
        """Return schedule, magic regex, and tasks without secrets."""
        data = await self._data()
        tasks = data.get("tasklist") or []
        if not isinstance(tasks, list):
            raise QasApiError(0, "tasklist is not a list")
        return {
            "crontab": data.get("crontab") or "",
            "magic_regex": data.get("magic_regex") or {},
            "tasks": [summarize_task(task) for task in tasks if isinstance(task, dict)],
        }

    async def share_detail(
        self,
        shareurl: str,
        task: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"shareurl": shareurl}
        if task:
            payload["task"] = task
        body = await self._json("POST", "/get_share_detail", json=payload)
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise QasApiError(0, "Unexpected share detail")
        return data

    async def savepath_detail(self, path: str) -> dict[str, Any]:
        body = await self._json("GET", "/get_savepath_detail", params={"path": path})
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise QasApiError(0, "Unexpected save path detail")
        return data

    async def search(self, query: str, *, deep: bool = False) -> list[dict[str, Any]]:
        body = await self._json(
            "GET",
            "/task_suggestions",
            params={"q": query, "d": "1" if deep else "0"},
        )
        data = body.get("data") if isinstance(body, dict) else None
        if data is None:
            return []
        if not isinstance(data, list):
            raise QasApiError(0, "Unexpected search response")
        return [item for item in data if isinstance(item, dict)]

    async def add_task(self, task: dict[str, Any]) -> dict[str, Any]:
        body = await self._json("POST", "/api/add_task", json=task)
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            return data
        return task

    async def replace_tasklist(self, tasklist: list[dict[str, Any]]) -> None:
        await self._json("POST", "/update", json={"tasklist": tasklist})

    async def run_tasks(self, tasklist: list[dict[str, Any]]) -> str:
        """Run the given tasks now and return the script log."""
        response = await self._send(
            "POST",
            "/run_script_now",
            json={"tasklist": tasklist},
            timeout=httpx.Timeout(self.settings.run_timeout, connect=30.0),
        )
        content_type = response.headers.get("content-type", "")
        text = response.text
        if response.is_error or "text/html" in content_type:
            self._parse_json(response)
        if "text/event-stream" in content_type or text.lstrip().startswith("data:"):
            return trim_log(parse_sse(text))
        self._parse_json(response)
        return trim_log(text.strip())
