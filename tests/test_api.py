import httpx2
import pytest
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi, format_detail
from tests.conftest import body_of


def test_format_detail_string_and_json():
    assert format_detail({"detail": "Invalid x. Valid: ['a']"}) == "Invalid x. Valid: ['a']"
    assert (
        format_detail({"detail": [{"loc": ["body", "x"], "msg": "bad"}]})
        == '[{"loc": ["body", "x"], "msg": "bad"}]'
    )
    assert format_detail({"error": "nope"}) == '{"error": "nope"}'
    assert format_detail("plain text") == "plain text"


async def test_get_returns_json(make_client):
    api = TeamarrApi(make_client(lambda r: httpx2.Response(200, json={"a": 1})), "http://t")
    assert await api.get("/api/v1/x", params={"q": "1"}) == {"a": 1}


async def test_put_sends_body(make_client):
    seen = {}

    def handler(r):
        seen["method"], seen["body"] = r.method, body_of(r)
        return httpx2.Response(200, json={"ok": True})

    api = TeamarrApi(make_client(handler), "http://t")
    await api.put("/api/v1/settings/lifecycle", json={"channel_range_start": 2000})
    assert seen == {"method": "PUT", "body": {"channel_range_start": 2000}}


async def test_400_becomes_tool_error_with_detail(make_client):
    api = TeamarrApi(
        make_client(
            lambda r: httpx2.Response(
                400, json={"detail": "Invalid channel_stability_mode. Valid: ['compact']"}
            )
        ),
        "http://t",
    )
    with pytest.raises(ToolError) as e:
        await api.put("/api/v1/settings/channel-numbering", json={})
    assert str(e.value) == (
        "HTTP 400 PUT /api/v1/settings/channel-numbering: "
        "Invalid channel_stability_mode. Valid: ['compact']"
    )


async def test_connection_error(make_client):
    def handler(r):
        raise httpx2.ConnectError("refused")

    api = TeamarrApi(make_client(handler), "http://192.168.1.63:9195")
    with pytest.raises(ToolError, match=r"Cannot reach Teamarr at http://192.168.1.63:9195"):
        await api.get("/health")


async def test_204_returns_none(make_client):
    api = TeamarrApi(make_client(lambda r: httpx2.Response(204)), "http://t")
    assert await api.request("DELETE", "/api/v1/teams/1") is None
