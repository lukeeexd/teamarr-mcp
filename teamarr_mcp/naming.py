"""Turn FastAPI's auto-generated operationIds into short, unique tool names."""

from __future__ import annotations

import re
from collections import Counter

from teamarr_mcp.spec import METHODS

# (METHOD, path) -> desired tool name. Resolves collisions after suffix stripping.
OVERRIDES: dict[tuple[str, str], str] = {
    ("PATCH", "/api/v1/teams/{team_id}"): "patch_team",
    ("GET", "/api/v1/detection-keywords"): "list_detection_keywords",
    ("POST", "/api/v1/detection-keywords"): "create_detection_keyword",
    ("GET", "/api/v1/detection-keywords/id/{keyword_id}"): "get_detection_keyword",
    ("PUT", "/api/v1/detection-keywords/id/{keyword_id}"): "update_detection_keyword",
    ("DELETE", "/api/v1/detection-keywords/id/{keyword_id}"): "delete_detection_keyword",
    ("PUT", "/api/v1/numbering-exceptions/{exception_id}"): "update_numbering_exception",
    ("DELETE", "/api/v1/numbering-exceptions/{exception_id}"): "delete_numbering_exception",
    ("GET", "/api/v1/dispatcharr/m3u-accounts/{account_id}/groups"): "list_m3u_account_groups",
}


def fastapi_suffix(path: str, method: str) -> str:
    return re.sub(r"\W", "_", path) + "_" + method.lower()


def strip_fastapi_suffix(operation_id: str, path: str, method: str) -> str:
    suffix = fastapi_suffix(path, method)
    if operation_id.endswith(suffix):
        return operation_id[: -len(suffix)]
    return operation_id


def _slug(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_").lower()
    name = re.sub(r"_+", "_", name)
    return name[:56] or "op"


def build_tool_names(spec: dict) -> dict[str, str]:
    routes: list[tuple[str, str, str]] = []  # (operationId, path, METHOD)
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            if method in METHODS and "operationId" in op:
                routes.append((op["operationId"], path, method.upper()))

    proposed: dict[str, str] = {}
    for op_id, path, method in routes:
        override = OVERRIDES.get((method, path))
        proposed[op_id] = _slug(override or strip_fastapi_suffix(op_id, path, method.lower()))

    counts = Counter(proposed.values())
    names: dict[str, str] = {}
    for op_id, path, method in routes:
        name = proposed[op_id]
        if counts[name] > 1 and (method, path) not in OVERRIDES:
            name = _slug(f"{name}_{method.lower()}")
        names[op_id] = name

    # Last resort for drift: number any remaining duplicates deterministically.
    seen: Counter[str] = Counter()
    final: dict[str, str] = {}
    for op_id, _, _ in routes:
        name = names[op_id]
        seen[name] += 1
        final[op_id] = name if seen[name] == 1 else _slug(f"{name}_{seen[name]}")
    return final
