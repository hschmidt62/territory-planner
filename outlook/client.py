from __future__ import annotations

import time
from typing import Any, Iterator

import requests

from .auth import get_access_token
from .config import GRAPH_BASE


class GraphError(RuntimeError):
    def __init__(self, status: int, payload: Any):
        super().__init__(f"Graph API error {status}: {payload}")
        self.status = status
        self.payload = payload


class GraphClient:
    """Thin wrapper around Microsoft Graph REST API.

    Handles auth, retries on 429/5xx with Retry-After, and pagination via @odata.nextLink.
    """

    def __init__(self, token: str | None = None, timeout: float = 30.0):
        self._token = token
        self._timeout = timeout
        self._session = requests.Session()

    def _auth_header(self) -> dict[str, str]:
        if self._token is None:
            self._token = get_access_token()
        return {"Authorization": f"Bearer {self._token}"}

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if not url.startswith("http"):
            url = f"{GRAPH_BASE}{url}"

        headers = kwargs.pop("headers", {}) or {}
        headers.update(self._auth_header())
        if "json" in kwargs and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        for attempt in range(4):
            resp = self._session.request(
                method, url, headers=headers, timeout=self._timeout, **kwargs
            )
            if resp.status_code == 401 and attempt == 0:
                # Token may have expired between cache check and call; force refresh.
                self._token = get_access_token()
                headers.update(self._auth_header())
                continue
            if resp.status_code in (429, 503, 504) and attempt < 3:
                delay = float(resp.headers.get("Retry-After", 2 ** attempt))
                time.sleep(delay)
                continue
            return resp
        return resp  # last response

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._request("GET", path, params=params)
        if not resp.ok:
            raise GraphError(resp.status_code, resp.text)
        return resp.json()

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._request("POST", path, json=json)
        if not resp.ok:
            raise GraphError(resp.status_code, resp.text)
        return resp.json() if resp.content else {}

    def patch(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        resp = self._request("PATCH", path, json=json)
        if not resp.ok:
            raise GraphError(resp.status_code, resp.text)
        return resp.json() if resp.content else {}

    def delete(self, path: str) -> None:
        resp = self._request("DELETE", path)
        if not resp.ok:
            raise GraphError(resp.status_code, resp.text)

    def paged(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_items: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Iterate over a collection endpoint, following @odata.nextLink."""
        count = 0
        page = self.get(path, params=params)
        while True:
            for item in page.get("value", []):
                yield item
                count += 1
                if max_items is not None and count >= max_items:
                    return
            next_link = page.get("@odata.nextLink")
            if not next_link:
                return
            page = self.get(next_link)
