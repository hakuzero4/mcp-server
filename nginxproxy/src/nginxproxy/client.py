"""Async HTTP client for the Nginx Proxy Manager REST API."""

from __future__ import annotations

from typing import Any

import httpx

from nginxproxy.exceptions import NpmApiError
from nginxproxy.settings import Settings


def normalize_api_url(url: str) -> str:
    """Return an API base URL ending in `/api` without a trailing slash."""
    cleaned = url.strip().rstrip("/")
    if not cleaned:
        raise ValueError("NPM URL is empty")
    if cleaned.endswith("/api"):
        return cleaned
    return f"{cleaned}/api"


def _error_message(status_code: int, body: Any) -> str:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if body.get("message"):
            return str(body["message"])
    if isinstance(body, str) and body.strip():
        return body.strip()
    return httpx.codes.get_reason_phrase(status_code) or "Unknown error"


def _parse_body(response: httpx.Response) -> Any:
    if response.status_code == 204 or not response.content:
        return {"ok": True}
    try:
        return response.json()
    except ValueError:
        text = response.text.strip()
        return {"ok": True, "raw": text} if text else {"ok": True}


class NpmClient:
    """JWT-authenticated client for Nginx Proxy Manager.

    Logs in with email/password on the first authenticated request and retries
    once after a 401 when credentials are available.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.api_url = normalize_api_url(self.settings.url)
        self._owned_http = http is None
        # Trailing slash + relative paths keeps `/api` in the URL (httpx drops
        # the last segment when base_url has no slash and the path starts with /).
        self._http = http or httpx.AsyncClient(
            base_url=f"{self.api_url}/",
            timeout=httpx.Timeout(self.settings.timeout),
            headers={"Accept": "application/json"},
        )
        self._token = self.settings.token.strip() or None

    async def aclose(self) -> None:
        if self._owned_http:
            await self._http.aclose()

    async def login(self) -> str:
        """Request a JWT from `POST /tokens` and store it for subsequent calls."""
        if not self.settings.email or not self.settings.password:
            raise NpmApiError(
                401,
                "Missing NPM credentials. Set NPM_EMAIL and NPM_PASSWORD, or NPM_TOKEN.",
            )
        response = await self._http.post(
            "tokens",
            json={"identity": self.settings.email, "secret": self.settings.password},
            headers={"Accept": "application/json"},
        )
        body = _parse_body(response)
        if response.is_error:
            raise NpmApiError(response.status_code, _error_message(response.status_code, body), body)
        token = body.get("token") if isinstance(body, dict) else None
        if not token:
            raise NpmApiError(response.status_code, "Login succeeded but no token was returned", body)
        self._token = str(token)
        return self._token

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return await self.request("POST", path, json=json, **kwargs)

    async def put(self, path: str, json: Any = None) -> Any:
        return await self.request("PUT", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        files: Any = None,
        timeout: httpx.Timeout | float | None = None,
        retry_on_unauthorized: bool = True,
    ) -> Any:
        relative = path.lstrip("/")
        if relative != "tokens" and self._token is None:
            await self.login()

        headers = {"Accept": "application/json"}
        if self._token and relative != "tokens":
            headers["Authorization"] = f"Bearer {self._token}"

        request_timeout = timeout if timeout is not None else self._timeout_for(method, relative)
        try:
            response = await self._http.request(
                method,
                relative,
                json=json,
                params=_drop_none(params),
                files=files,
                headers=headers,
                timeout=request_timeout,
            )
        except httpx.HTTPError as exc:
            raise NpmApiError(0, f"HTTP request failed: {exc}") from exc

        if response.status_code == 401 and retry_on_unauthorized and relative != "tokens":
            if self.settings.email and self.settings.password:
                await self.login()
                return await self.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    files=files,
                    timeout=timeout,
                    retry_on_unauthorized=False,
                )

        body = _parse_body(response)
        if response.is_error:
            raise NpmApiError(response.status_code, _error_message(response.status_code, body), body)
        return body

    def _timeout_for(self, method: str, path: str) -> httpx.Timeout | None:
        if method.upper() == "POST" and "nginx/certificates" in path:
            return httpx.Timeout(self.settings.cert_timeout)
        return None


def _drop_none(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if not params:
        return None
    return {key: value for key, value in params.items() if value is not None}
