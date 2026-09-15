"""Load the Teamarr OpenAPI spec: explicit file, else live instance, else vendored copy."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

import httpx2

from teamarr_mcp.config import Settings

log = logging.getLogger(__name__)

METHODS = ("get", "post", "put", "patch", "delete")


def count_operations(spec: dict) -> int:
    return sum(1 for ops in spec.get("paths", {}).values() for m in ops if m in METHODS)


def load_vendored() -> dict:
    text = resources.files("teamarr_mcp").joinpath("specs/openapi.json").read_text("utf-8")
    return json.loads(text)


@dataclass(frozen=True)
class LoadedSpec:
    spec: dict
    source: Literal["live", "file", "vendored"]
    version: str
    operation_count: int

    @classmethod
    def build(cls, spec: dict, source: Literal["live", "file", "vendored"]) -> LoadedSpec:
        return cls(
            spec=spec,
            source=source,
            version=str(spec.get("info", {}).get("version", "unknown")),
            operation_count=count_operations(spec),
        )


async def load_spec(settings: Settings, client: httpx2.AsyncClient) -> LoadedSpec:
    if settings.openapi_path:
        path = Path(settings.openapi_path)
        if not path.is_file():
            raise FileNotFoundError(f"TEAMARR_OPENAPI_PATH not found: {path}")
        return LoadedSpec.build(json.loads(path.read_text("utf-8")), "file")

    try:
        resp = await client.get("/openapi.json", timeout=10.0)
        if resp.status_code == 200:
            return LoadedSpec.build(resp.json(), "live")
        log.warning(
            "Teamarr returned HTTP %s for /openapi.json; using vendored spec", resp.status_code
        )
    except httpx2.HTTPError as exc:
        log.warning("Could not fetch %s/openapi.json (%s); using vendored spec", settings.url, exc)
    return LoadedSpec.build(load_vendored(), "vendored")
