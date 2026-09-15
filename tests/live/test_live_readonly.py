import os

import pytest
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server

URL = os.environ.get("TEAMARR_TEST_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEAMARR_TEST_URL not set")


@pytest.fixture
async def client():
    mcp = await build_server(Settings(url=URL, read_only=True))
    async with Client(mcp) as c:
        yield c


async def test_info_reports_live_spec(client):
    info = (await client.call_tool("teamarr_info", {})).data
    assert info["spec_source"] == "live"
    assert info["health"]["status"] == "healthy"
    assert info["teamarr_version"] == info["spec_version"]


async def test_generated_get_works(client):
    r = await client.call_tool("get_lifecycle_settings", {})
    assert "channel_create_timing" in str(r.data)


async def test_summary_returns_rows(client):
    res = (await client.call_tool("get_event_channels_summary", {})).data
    assert res["count"] >= 0
    if res["channels"]:
        assert res["channels"][0]["channel_number"] is not None


async def test_unmatched_streams(client):
    res = (await client.call_tool("find_unmatched_streams", {"limit": 20})).data
    assert "by_reason" in res


async def test_tsdb_check(client):
    res = (await client.call_tool("check_tsdb_gated_subscriptions", {})).data
    assert isinstance(res["tsdb_key_configured"], bool)


async def test_read_only_hides_writes(client):
    names = {t.name for t in await client.list_tools()}
    assert "update_settings" not in names and "create_team" not in names
