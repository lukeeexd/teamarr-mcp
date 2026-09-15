from __future__ import annotations

from fastmcp import FastMCP

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext


def _items(payload, key: str) -> list[dict]:
    return payload if isinstance(payload, list) else payload.get(key, [])


def resolve_template(templates: list[dict], league: str | None, sport: str | None) -> dict | None:
    events = [t for t in templates if t.get("template_type") == "event"]
    for t in events:
        for a in t.get("global_assignments") or []:
            if league and league in (a.get("leagues") or []):
                return t
    for t in events:
        for a in t.get("global_assignments") or []:
            if sport and sport in (a.get("sports") or []):
                return t
    return None


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    @mcp.tool(tags={"teamarr", "read"})
    async def get_event_channels_summary(include_deleted: bool = False) -> dict:
        """One-call overview of Teamarr's live and upcoming event channels: channel number,
        name, event, league, source group (with its stream count), the event template that
        applies, Dispatcharr channel id, tvg-id and sync status. Sorted by channel number."""
        channels = _items(
            await api.get(
                "/api/v1/channels/managed",
                params={"include_deleted": str(include_deleted).lower()},
            ),
            "channels",
        )
        groups = {g["id"]: g for g in _items(await api.get("/api/v1/groups"), "groups")}
        templates = _items(await api.get("/api/v1/templates"), "templates")
        rows = []
        for ch in channels:
            g = groups.get(ch.get("event_epg_group_id"))
            t = resolve_template(templates, ch.get("league"), ch.get("sport"))
            rows.append(
                {
                    "channel_number": ch.get("channel_number"),
                    "channel_name": ch.get("channel_name"),
                    "event_name": ch.get("event_name"),
                    "event_date": ch.get("event_date"),
                    "sport": ch.get("sport"),
                    "league": ch.get("league"),
                    "sync_status": ch.get("sync_status"),
                    "group_id": ch.get("event_epg_group_id"),
                    "group_name": (g.get("display_name") or g.get("name")) if g else None,
                    "group_stream_count": g.get("stream_count") if g else None,
                    "template_id": t["id"] if t else None,
                    "template_name": t["name"] if t else None,
                    "dispatcharr_channel_id": ch.get("dispatcharr_channel_id"),
                    "tvg_id": ch.get("tvg_id"),
                }
            )
        rows.sort(key=lambda r: (r["channel_number"] is None, r["channel_number"] or 0))
        return {"count": len(rows), "channels": rows}

    ctx.curated_tool_names.append("get_event_channels_summary")
