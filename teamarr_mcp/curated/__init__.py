"""Hand-written tools that encode Teamarr API footguns."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastmcp import FastMCP

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.config import Settings
from teamarr_mcp.spec import LoadedSpec


@dataclass
class ServerContext:
    settings: Settings
    loaded: LoadedSpec
    generated_tool_count: int
    curated_tool_names: list[str] = field(default_factory=list)


def register_all(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    from teamarr_mcp.curated import channels, info, matching, settings, subscriptions, templates

    for module in (info, settings, templates, channels, matching, subscriptions):
        module.register(mcp, api, ctx)
