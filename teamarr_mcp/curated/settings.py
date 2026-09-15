from __future__ import annotations

import re

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext

MASK = "********"
_BLOCK_RE = re.compile(r"^/api/v1/settings/([^/{}]+)$")


def settings_blocks(spec: dict) -> list[str]:
    blocks = []
    for path, ops in spec.get("paths", {}).items():
        m = _BLOCK_RE.match(path)
        if m and "get" in ops and "put" in ops:
            blocks.append(m.group(1))
    return sorted(blocks)


def merge_block(current: dict, changes: dict) -> dict:
    merged = {k: v for k, v in current.items() if v != MASK}
    merged.update(changes)
    return merged


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    if ctx.settings.read_only:
        return
    blocks = settings_blocks(ctx.loaded.spec)

    async def update_settings(block: str, changes: dict, replace: bool = False) -> dict:
        if block not in blocks:
            raise ToolError(f"Unknown settings block '{block}'. Available: {', '.join(blocks)}")
        path = f"/api/v1/settings/{block}"
        payload = changes if replace else merge_block(await api.get(path), changes)
        return await api.put(path, json=payload)

    update_settings.__doc__ = f"""Safely change fields in a Teamarr settings block.

Teamarr's PUT /api/v1/settings/<block> replaces the WHOLE block: any field you omit is reset
to its default (e.g. `channel_range_start` on `lifecycle`, `epg_id` /
`default_channel_group_id` on `dispatcharr`). This tool GETs the block, merges your `changes`
over it, and PUTs the result. Masked secrets (`********`) are dropped so the server keeps the
stored value. Set `replace=True` to PUT `changes` verbatim.

Blocks available on this instance: {", ".join(blocks)}. Invalid enum values return Teamarr's
400 message listing the valid options.
"""
    mcp.tool(update_settings, tags={"teamarr", "write"})
    ctx.curated_tool_names.append("update_settings")
