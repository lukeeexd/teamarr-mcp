import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server


def _handler(r: httpx2.Request):
    if r.url.path == "/openapi.json":
        raise httpx2.ConnectError("offline")  # force vendored
    if r.url.path == "/health":
        return httpx2.Response(200, json={"status": "healthy", "version": "2.17.0"})
    return httpx2.Response(200, json={})


async def test_build_server_has_generated_and_curated_tools(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler))
    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
    assert "list_teams" in names
    assert "teamarr_info" in names
    assert "update_lifecycle_settings" not in names


async def test_teamarr_info(make_client):
    mcp = await build_server(Settings(url="http://t", read_only=True), client=make_client(_handler))
    async with Client(mcp) as c:
        info = (await c.call_tool("teamarr_info", {})).data
    assert info["teamarr_url"] == "http://t"
    assert info["teamarr_version"] == "2.17.0"
    assert info["health"]["status"] == "healthy"
    assert info["spec_source"] == "vendored"
    assert info["spec_version"] == "2.17.0"
    assert info["read_only"] is True
    assert info["destructive_enabled"] is False
    assert info["generated_tools"] > 100
    assert info["curated_tools"] >= 1
