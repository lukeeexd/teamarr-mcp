import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.curated.templates import UPDATE_KEYS_FALLBACK, update_body
from teamarr_mcp.server import build_server
from tests.conftest import body_of


def _full(i, ttype, post_title="Postgame"):
    return {
        "id": i,
        "name": f"T{i}",
        "template_type": ttype,
        "created_at": "x",
        "updated_at": "y",
        "team_count": 0,
        "global_assignments": None,
        "title_format": "{gracenote_category}",
        "pregame_fallback": {
            "title": "Coming up",
            "subtitle": "",
            "description": "",
            "description_fallback": "",
            "art_url": "",
        },
        "postgame_fallback": {
            "title": post_title,
            "subtitle": "",
            "description": "",
            "art_url": "",
        },
    }


def test_update_body_strips_readonly_keys(vendored_spec):
    body = update_body(_full(1, "event"), vendored_spec)
    assert "id" not in body and "created_at" not in body and "team_count" not in body
    assert "postgame_fallback" in body and "title_format" in body
    assert set(UPDATE_KEYS_FALLBACK) >= set(body)


def _handler_factory(templates: dict, puts: list):
    def handler(r: httpx2.Request):
        if r.url.path == "/openapi.json":
            raise httpx2.ConnectError("offline")
        if r.url.path == "/api/v1/templates":
            return httpx2.Response(
                200,
                json={
                    "templates": [
                        {"id": t["id"], "name": t["name"], "template_type": t["template_type"]}
                        for t in templates.values()
                    ]
                },
            )
        for tid, t in templates.items():
            if r.url.path == f"/api/v1/templates/{tid}":
                if r.method == "PUT":
                    puts.append((tid, body_of(r)))
                    if tid == 4:
                        return httpx2.Response(400, json={"detail": "bad template"})
                    t.update(body_of(r))
                return httpx2.Response(200, json=t)
        return httpx2.Response(404, json={"detail": "Not found"})

    return handler


async def test_bulk_edit_event_templates_only(make_client):
    templates = {
        1: _full(1, "team"),
        2: _full(2, "event"),
        3: _full(3, "event", "New text"),
        4: _full(4, "event"),
    }
    puts = []
    mcp = await build_server(
        Settings(url="http://t"), client=make_client(_handler_factory(templates, puts))
    )
    async with Client(mcp) as c:
        res = (
            await c.call_tool(
                "set_template_filler",
                {"section": "postgame", "field": "title", "text": "New text"},
            )
        ).data
    assert res["changed"] == [2]
    assert res["unchanged"] == [3]
    assert res["skipped"] == [{"id": 1, "reason": "template_type=team"}]
    assert res["failed"][0]["id"] == 4 and "bad template" in res["failed"][0]["error"]
    put_ids = [p[0] for p in puts]
    assert put_ids == [2, 4]
    assert puts[0][1]["postgame_fallback"]["title"] == "New text"
    assert puts[0][1]["postgame_fallback"]["subtitle"] == ""  # other keys preserved
    assert "id" not in puts[0][1]


async def test_explicit_ids_bypass_type_filter(make_client):
    templates = {1: _full(1, "team"), 2: _full(2, "event")}
    puts = []
    mcp = await build_server(
        Settings(url="http://t"), client=make_client(_handler_factory(templates, puts))
    )
    async with Client(mcp) as c:
        res = (
            await c.call_tool(
                "set_template_filler",
                {
                    "section": "pregame",
                    "field": "description",
                    "text": "{relative_day_title}",
                    "template_ids": [1],
                },
            )
        ).data
    assert res["changed"] == [1] and res["skipped"] == []
    assert puts[0][1]["pregame_fallback"]["description"] == "{relative_day_title}"
