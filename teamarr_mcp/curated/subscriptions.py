from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext


def _list(payload, key: str) -> list:
    return payload if isinstance(payload, list) else payload.get(key, [])


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    @mcp.tool(tags={"teamarr", "read"})
    async def check_tsdb_gated_subscriptions() -> dict:
        """Find subscribed leagues that will produce NO fixtures because they come from
        TheSportsDB, which Teamarr only supports with a premium API key. Also counts custom
        leagues (always TSDB-backed). Use this when a subscribed league shows no events.
        The key is set via `update_settings(block="display", changes={"tsdb_api_key": ...})`."""
        display = await api.get("/api/v1/settings/display")
        has_key = bool(display.get("tsdb_api_key"))
        subscribed = set((await api.get("/api/v1/sports-subscription")).get("leagues") or [])
        leagues = _list(await api.get("/api/v1/cache/leagues"), "leagues")
        try:
            custom_count = len(_list(await api.get("/api/v1/leagues/custom"), "leagues"))
        except ToolError:
            custom_count = 0
        gated = (
            []
            if has_key
            else [
                {"slug": lg["slug"], "name": lg.get("name"), "sport": lg.get("sport")}
                for lg in leagues
                if lg.get("provider") == "tsdb" and lg.get("slug") in subscribed
            ]
        )
        gated.sort(key=lambda x: x["slug"])
        if has_key:
            message = "A TheSportsDB premium key is configured; no subscriptions are gated."
        elif gated or custom_count:
            message = (
                f"{len(gated)} subscribed league(s) and {custom_count} custom league(s) "
                "need a TheSportsDB premium key and currently return no fixtures."
            )
        else:
            message = "No TheSportsDB-backed subscriptions; no premium key needed."
        return {
            "tsdb_key_configured": has_key,
            "gated_leagues": gated,
            "custom_leagues_count": custom_count,
            "message": message,
        }

    ctx.curated_tool_names.append("check_tsdb_gated_subscriptions")
