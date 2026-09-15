"""Ordered route maps: always-excluded, read-only gate, destructive gate, then tools."""

from __future__ import annotations

import re

from fastmcp.server.providers.openapi import MCPType, RouteMap
from fastmcp.utilities.openapi import HTTPRoute

from teamarr_mcp.config import Settings

# (METHOD or "*", anchored regex on path)
ALWAYS_EXCLUDED: list[tuple[str, str]] = [
    ("GET", r"^/api/v1/support/bundle$"),  # large archive
    ("GET", r"^/api/v1/backup/file/[^/]+$"),  # binary download
    ("GET", r"^/api/v1/backup$"),  # binary download of latest backup
    ("GET", r"^/api/v1/epg/xmltv$"),  # whole XMLTV document
    ("GET", r"^/api/v1/groups/[^/]+/xmltv$"),
    ("GET", r"^/api/v1/groups/xmltv/combined$"),
    ("GET", r"^/api/v1/epg/generate/stream$"),  # SSE stream
    # Whole-block settings PUTs are replaced by the curated update_settings tool.
    ("PUT", r"^/api/v1/settings/(?!stream-ordering/scopes/)[^/]+(/[^/]+)*$"),
]

DESTRUCTIVE: list[tuple[str, str]] = [
    ("DELETE", r".*"),
    ("POST", r"^/api/v1/backup$"),
    ("POST", r"^/api/v1/backup/[^/]+/restore$"),
    ("POST", r"^/api/v1/templates/restore-defaults$"),
    ("POST", r"^/api/v1/channels/reset$"),
    ("POST", r"^/api/v1/groups/cache/clear(-all)?$"),
    ("POST", r"^/api/v1/groups/[^/]+/cache/clear$"),
    ("POST", r"^/api/v1/game-data-cache/clear$"),
]


def _matches(rules: list[tuple[str, str]], method: str, path: str) -> bool:
    return any(
        (m == "*" or m == method.upper()) and re.search(pattern, path) for m, pattern in rules
    )


def is_destructive(method: str, path: str) -> bool:
    return _matches(DESTRUCTIVE, method, path)


def _maps(rules: list[tuple[str, str]], mcp_type: MCPType) -> list[RouteMap]:
    return [
        RouteMap(methods="*" if m == "*" else [m], pattern=p, mcp_type=mcp_type) for m, p in rules
    ]


def build_route_maps(settings: Settings) -> list[RouteMap]:
    maps = _maps(ALWAYS_EXCLUDED, MCPType.EXCLUDE)
    if settings.read_only:
        maps.append(
            RouteMap(
                methods=["POST", "PUT", "PATCH", "DELETE"], pattern=r".*", mcp_type=MCPType.EXCLUDE
            )
        )
    if not settings.enable_destructive:
        maps += _maps(DESTRUCTIVE, MCPType.EXCLUDE)
    maps.append(RouteMap(mcp_type=MCPType.TOOL))
    return maps


def component_fn(route: HTTPRoute, component) -> None:
    """Tag components and flag destructive ones in the description."""
    component.tags.add("teamarr")
    component.tags.add("read" if route.method.upper() == "GET" else "write")
    if is_destructive(route.method, route.path):
        component.tags.add("destructive")
        component.description = "[destructive] " + (component.description or "")
