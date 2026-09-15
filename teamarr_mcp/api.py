"""Thin async wrapper over httpx2 that turns Teamarr errors into ToolErrors."""

from __future__ import annotations

import json as _json
from typing import Any

import httpx2
from fastmcp.exceptions import ToolError


def format_detail(payload: Any) -> str:
    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
        return detail if isinstance(detail, str) else _json.dumps(detail)
    if isinstance(payload, str):
        return payload
    return _json.dumps(payload)


class TeamarrApi:
    def __init__(self, client: httpx2.AsyncClient, base_url: str) -> None:
        self._client = client
        self.base_url = base_url

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        try:
            resp = await self._client.request(method, path, params=params, json=json)
        except httpx2.HTTPError as exc:
            raise ToolError(f"Cannot reach Teamarr at {self.base_url}: {exc}") from exc
        if resp.status_code >= 400:
            try:
                payload: Any = resp.json()
            except ValueError:
                payload = resp.text
            raise ToolError(
                f"HTTP {resp.status_code} {method.upper()} {path}: {format_detail(payload)}"
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def put(self, path: str, json: Any) -> Any:
        return await self.request("PUT", path, json=json)

    async def post(self, path: str, json: Any = None) -> Any:
        return await self.request("POST", path, json=json)
