from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    @mcp.tool(tags={"teamarr", "read"})
    async def teamarr_info() -> dict:
        """Report the connected Teamarr instance, its version, and how this MCP server
        is configured (spec source, tool counts, read-only / destructive flags).
        Call this first if a tool you expected is missing."""
        try:
            health = await api.get("/health")
        except ToolError as exc:
            health = {"status": "unreachable", "error": str(exc)}
        return {
            "teamarr_url": ctx.settings.url,
            "teamarr_version": health.get("version") if isinstance(health, dict) else None,
            "health": health,
            "spec_source": ctx.loaded.source,
            "spec_version": ctx.loaded.version,
            "generated_tools": ctx.generated_tool_count,
            "curated_tools": len(ctx.curated_tool_names),
            "read_only": ctx.settings.read_only,
            "destructive_enabled": ctx.settings.enable_destructive,
        }

    ctx.curated_tool_names.append("teamarr_info")
