import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server

FAILS = {
    "count": 3,
    "run_id": 137,
    "group_id": None,
    "reason_filter": None,
    "failures": [
        {
            "id": 1,
            "run_id": 137,
            "group_id": 2,
            "group_name": "PPV",
            "stream_id": 11,
            "stream_name": "EVENT 01: X",
            "reason": "no_event_card_match",
            "detail": "No matching event card",
            "parsed_team1": None,
            "parsed_team2": None,
            "detected_league": None,
        },
        {
            "id": 2,
            "run_id": 137,
            "group_id": 2,
            "group_name": "PPV",
            "stream_id": 12,
            "stream_name": "EVENT 02: Y",
            "reason": "unmatched",
            "detail": "",
            "parsed_team1": "A",
            "parsed_team2": "B",
            "detected_league": "ufc",
        },
        {
            "id": 3,
            "run_id": 137,
            "group_id": 3,
            "group_name": "Sky",
            "stream_id": 13,
            "stream_name": "S 01: Z",
            "reason": "unmatched",
            "detail": "",
            "parsed_team1": None,
            "parsed_team2": None,
            "detected_league": None,
        },
    ],
}
GROUPS = {
    "groups": [
        {
            "id": 2,
            "name": "PPV Events | 1",
            "display_name": "PPV",
            "custom_regex_teams": r"(.+) v (.+)",
            "custom_regex_teams_enabled": True,
            "custom_regex_time": None,
            "custom_regex_time_enabled": False,
            "stream_include_regex": "EVENT",
            "stream_include_regex_enabled": True,
            "stream_timezone": "US/Eastern",
        },
        {"id": 3, "name": "Sky", "display_name": None, "custom_regex_teams_enabled": False},
    ]
}


def handler(r: httpx2.Request):
    if r.url.path == "/openapi.json":
        raise httpx2.ConnectError("offline")
    if r.url.path == "/api/v1/epg/failed-matches":
        assert r.url.params.get("limit") == "200"
        assert "group_id" not in r.url.params
        return httpx2.Response(200, json=FAILS)
    if r.url.path == "/api/v1/groups":
        return httpx2.Response(200, json=GROUPS)
    return httpx2.Response(404, json={"detail": "nf"})


async def test_groups_failures_with_regex_context(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(handler))
    async with Client(mcp) as c:
        res = (await c.call_tool("find_unmatched_streams", {})).data
    assert res["run_id"] == 137 and res["count"] == 3
    assert res["by_reason"] == {"no_event_card_match": 1, "unmatched": 2}
    ppv = next(g for g in res["groups"] if g["group_id"] == 2)
    assert ppv["group_name"] == "PPV"
    assert ppv["regex"] == {
        "teams": r"(.+) v (.+)",
        "stream_include": "EVENT",
        "stream_timezone": "US/Eastern",
    }
    assert [s["stream_id"] for s in ppv["streams"]] == [11, 12]
    assert ppv["streams"][1]["parsed_team1"] == "A"
    sky = next(g for g in res["groups"] if g["group_id"] == 3)
    assert sky["regex"] == {}
    assert sky["group_name"] == "Sky"
