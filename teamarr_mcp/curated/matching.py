from __future__ import annotations

from collections import Counter

from fastmcp import FastMCP

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext

_REGEX_FIELDS = ("teams", "time", "date", "day", "month", "league", "event_name", "fighters")


def active_regexes(group: dict) -> dict:
    out = {}
    for f in _REGEX_FIELDS:
        if group.get(f"custom_regex_{f}_enabled") and group.get(f"custom_regex_{f}"):
            out[f] = group[f"custom_regex_{f}"]
    for f in ("stream_include", "stream_exclude"):
        if group.get(f"{f}_regex_enabled") and group.get(f"{f}_regex"):
            out[f] = group[f"{f}_regex"]
    if group.get("stream_timezone"):
        out["stream_timezone"] = group["stream_timezone"]
    return out


def _list(payload, key: str) -> list[dict]:
    return payload if isinstance(payload, list) else payload.get(key, [])


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    @mcp.tool(tags={"teamarr", "read"})
    async def find_unmatched_streams(
        group_id: int | None = None, reason: str | None = None, limit: int = 200
    ) -> dict:
        """Streams in your source groups that produced no event channel in the latest EPG
        run, grouped by source group with that group's active custom regexes and timezone
        alongside, so you can tune parsing for provider naming formats such as
        `Team1 HH:MM Team2 DD/MM`. Reasons include `unmatched`, `no_event_card_match`,
        `excluded_league`. Filter with `group_id` and/or `reason`."""
        params: dict = {"limit": limit}
        if group_id is not None:
            params["group_id"] = group_id
        if reason:
            params["reason"] = reason
        failed = await api.get("/api/v1/epg/failed-matches", params=params)
        failures = _list(failed, "failures")
        groups = {g["id"]: g for g in _list(await api.get("/api/v1/groups"), "groups")}
        by_group: dict[int, list[dict]] = {}
        for f in failures:
            by_group.setdefault(f.get("group_id"), []).append(
                {
                    "stream_id": f.get("stream_id"),
                    "stream_name": f.get("stream_name"),
                    "reason": f.get("reason"),
                    "detail": f.get("detail"),
                    "parsed_team1": f.get("parsed_team1"),
                    "parsed_team2": f.get("parsed_team2"),
                    "detected_league": f.get("detected_league"),
                }
            )
        out_groups = []
        for gid, streams in by_group.items():
            g = groups.get(gid, {})
            fallback_name = next(
                (f["group_name"] for f in failures if f.get("group_id") == gid), None
            )
            out_groups.append(
                {
                    "group_id": gid,
                    "group_name": g.get("display_name") or g.get("name") or fallback_name,
                    "regex": active_regexes(g),
                    "streams": streams,
                }
            )
        return {
            "run_id": failed.get("run_id") if isinstance(failed, dict) else None,
            "count": len(failures),
            "by_reason": dict(sorted(Counter(f.get("reason") for f in failures).items())),
            "groups": out_groups,
        }

    ctx.curated_tool_names.append("find_unmatched_streams")
