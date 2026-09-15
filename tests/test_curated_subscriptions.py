import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server


def make_handler(key):
    def handler(r: httpx2.Request):
        if r.url.path == "/openapi.json":
            raise httpx2.ConnectError("offline")
        if r.url.path == "/api/v1/settings/display":
            return httpx2.Response(200, json={"tsdb_api_key": key})
        if r.url.path == "/api/v1/sports-subscription":
            return httpx2.Response(200, json={"leagues": ["nfl", "ipl", "sa20"]})
        if r.url.path == "/api/v1/cache/leagues":
            return httpx2.Response(
                200,
                json={
                    "count": 4,
                    "leagues": [
                        {"slug": "nfl", "provider": "espn", "name": "NFL", "sport": "football"},
                        {"slug": "ipl", "provider": "tsdb", "name": "IPL", "sport": "cricket"},
                        {"slug": "sa20", "provider": "tsdb", "name": "SA20", "sport": "cricket"},
                        {"slug": "bbl", "provider": "tsdb", "name": "BBL", "sport": "cricket"},
                    ],
                },
            )
        if r.url.path == "/api/v1/leagues/custom":
            return httpx2.Response(200, json=[{"slug": "my-league"}])
        return httpx2.Response(404, json={"detail": "nf"})

    return handler


async def test_gated_when_no_key(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(make_handler(None)))
    async with Client(mcp) as c:
        res = (await c.call_tool("check_tsdb_gated_subscriptions", {})).data
    assert res["tsdb_key_configured"] is False
    assert [g["slug"] for g in res["gated_leagues"]] == ["ipl", "sa20"]
    assert res["custom_leagues_count"] == 1
    assert "premium" in res["message"].lower()


async def test_nothing_gated_with_key(make_client):
    mcp = await build_server(
        Settings(url="http://t"), client=make_client(make_handler("********"))
    )
    async with Client(mcp) as c:
        res = (await c.call_tool("check_tsdb_gated_subscriptions", {})).data
    assert res["tsdb_key_configured"] is True
    assert res["gated_leagues"] == []
