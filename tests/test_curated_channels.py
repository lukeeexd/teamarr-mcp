import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server

CHANNELS = {
    "channels": [
        {
            "id": 1,
            "channel_number": "2003",
            "channel_name": "MLB 03 | A at B",
            "event_name": "A at B",
            "event_date": "2026-09-15 18:40",
            "sport": "baseball",
            "league": "mlb",
            "sync_status": "synced",
            "event_epg_group_id": 7,
            "dispatcharr_channel_id": 900,
            "tvg_id": "teamarr-event-1-x",
            "deleted_at": None,
        },
        {
            "id": 2,
            "channel_number": "10",
            "channel_name": "UFC",
            "event_name": "Fight",
            "event_date": "x",
            "sport": "mma",
            "league": "ufc",
            "sync_status": "pending",
            "event_epg_group_id": 99,
            "dispatcharr_channel_id": None,
            "tvg_id": "t2",
            "deleted_at": None,
        },
    ],
    "total": 2,
}
GROUPS = {
    "groups": [{"id": 7, "name": "USA | MLB", "display_name": "MLB", "stream_count": 30}],
    "total": 1,
}
TEMPLATES = {
    "templates": [
        {
            "id": 5,
            "name": "College",
            "template_type": "event",
            "global_assignments": [{"sports": None, "leagues": ["ncaaf"]}],
        },
        {
            "id": 6,
            "name": "Baseball",
            "template_type": "event",
            "global_assignments": [{"sports": ["baseball"], "leagues": None}],
        },
        {"id": 1, "name": "Team", "template_type": "team", "global_assignments": None},
    ]
}


def handler(r: httpx2.Request):
    if r.url.path == "/openapi.json":
        raise httpx2.ConnectError("offline")
    if r.url.path == "/api/v1/channels/managed":
        assert r.url.params.get("include_deleted") == "false"
        return httpx2.Response(200, json=CHANNELS)
    if r.url.path == "/api/v1/groups":
        return httpx2.Response(200, json=GROUPS)
    if r.url.path == "/api/v1/templates":
        return httpx2.Response(200, json=TEMPLATES)
    return httpx2.Response(404, json={"detail": "nf"})


async def test_summary_joins_groups_and_templates(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(handler))
    async with Client(mcp) as c:
        res = (await c.call_tool("get_event_channels_summary", {})).data
    assert res["count"] == 2
    first, second = res["channels"]
    assert first["channel_number"] == 10  # numeric sort, not lexicographic ("10" < "2003")
    assert first["group_name"] is None and first["template_name"] is None
    assert second["group_name"] == "MLB" and second["group_stream_count"] == 30
    assert second["template_id"] == 6 and second["template_name"] == "Baseball"
    assert second["tvg_id"] == "teamarr-event-1-x"
