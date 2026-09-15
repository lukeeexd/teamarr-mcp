import httpx2
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from teamarr_mcp.config import Settings
from teamarr_mcp.curated.settings import merge_block, settings_blocks
from teamarr_mcp.server import build_server
from tests.conftest import body_of

LIFECYCLE = {
    "channel_create_timing": "before_event",
    "channel_delete_timing": "after_event",
    "channel_pre_buffer_minutes": 1440,
    "channel_post_buffer_minutes": 120,
    "channel_range_start": 2000,
    "channel_range_end": None,
}
DISPATCHARR = {
    "enabled": True,
    "url": "http://d:9191",
    "username": "Luke",
    "password": "********",
    "epg_id": 24,
    "default_channel_profile_ids": [1],
    "default_stream_profile_id": None,
    "default_channel_group_id": 652,
    "default_channel_group_mode": "Events | {sport}",
    "cleanup_unused_logos": True,
}


def test_merge_keeps_unmentioned_fields():
    merged = merge_block(LIFECYCLE, {"channel_post_buffer_minutes": 180})
    assert merged["channel_range_start"] == 2000
    assert merged["channel_post_buffer_minutes"] == 180


def test_merge_drops_masked_secret_unless_set():
    merged = merge_block(DISPATCHARR, {"epg_id": 25})
    assert "password" not in merged
    assert merged["default_channel_group_id"] == 652
    merged2 = merge_block(DISPATCHARR, {"password": "new"})
    assert merged2["password"] == "new"


def test_settings_blocks_from_spec(vendored_spec):
    blocks = settings_blocks(vendored_spec)
    assert {"lifecycle", "dispatcharr", "channel-numbering", "epg"} <= set(blocks)
    assert "tsdb" not in blocks  # only has POST validate-key


def _handler_factory(store: dict, calls: list):
    def handler(r: httpx2.Request):
        if r.url.path == "/openapi.json":
            raise httpx2.ConnectError("offline")
        calls.append((r.method, r.url.path, body_of(r) if r.method == "PUT" else None))
        if r.url.path == "/api/v1/settings/lifecycle":
            if r.method == "PUT":
                store.update(body_of(r))
            return httpx2.Response(200, json=store)
        if r.url.path == "/api/v1/settings/channel-numbering" and r.method == "PUT":
            return httpx2.Response(
                400,
                json={
                    "detail": "Invalid channel_stability_mode. Valid: ['compact', 'gap', 'strict']"
                },
            )
        if r.url.path == "/api/v1/settings/channel-numbering":
            return httpx2.Response(200, json={"channel_stability_mode": "compact"})
        return httpx2.Response(200, json={})

    return handler


async def test_update_settings_merges_then_puts(make_client):
    store, calls = dict(LIFECYCLE), []
    mcp = await build_server(
        Settings(url="http://t"), client=make_client(_handler_factory(store, calls))
    )
    async with Client(mcp) as c:
        result = (
            await c.call_tool(
                "update_settings",
                {"block": "lifecycle", "changes": {"channel_post_buffer_minutes": 180}},
            )
        ).data
    put = [c for c in calls if c[0] == "PUT"][0]
    assert put[2]["channel_range_start"] == 2000
    assert put[2]["channel_post_buffer_minutes"] == 180
    assert result["channel_post_buffer_minutes"] == 180


async def test_update_settings_replace_sends_changes_verbatim(make_client):
    store, calls = dict(LIFECYCLE), []
    mcp = await build_server(
        Settings(url="http://t"), client=make_client(_handler_factory(store, calls))
    )
    async with Client(mcp) as c:
        await c.call_tool(
            "update_settings",
            {"block": "lifecycle", "changes": {"channel_range_start": 3000}, "replace": True},
        )
    assert [c for c in calls if c[0] == "GET" and "lifecycle" in c[1]] == []
    assert [c for c in calls if c[0] == "PUT"][0][2] == {"channel_range_start": 3000}


async def test_update_settings_surfaces_enum_error(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler_factory({}, [])))
    async with Client(mcp) as c:
        with pytest.raises(ToolError, match=r"Valid: \['compact', 'gap', 'strict'\]"):
            await c.call_tool(
                "update_settings",
                {"block": "channel-numbering", "changes": {"channel_stability_mode": "bogus"}},
            )


async def test_update_settings_unknown_block(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler_factory({}, [])))
    async with Client(mcp) as c:
        with pytest.raises(ToolError, match="Unknown settings block 'nope'"):
            await c.call_tool("update_settings", {"block": "nope", "changes": {}})


async def test_update_settings_hidden_in_read_only(make_client):
    mcp = await build_server(
        Settings(url="http://t", read_only=True), client=make_client(_handler_factory({}, []))
    )
    async with Client(mcp) as c:
        assert "update_settings" not in {t.name for t in await c.list_tools()}
