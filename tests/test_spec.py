import json

import httpx2
import pytest

from teamarr_mcp.config import Settings
from teamarr_mcp.spec import LoadedSpec, count_operations, load_spec, load_vendored


def test_vendored_spec_shape():
    spec = load_vendored()
    assert spec["info"]["title"] == "Teamarr API"
    assert len(spec["paths"]) == 164
    assert count_operations(spec) == 225


async def test_live_spec_preferred(make_client):
    live = {
        "openapi": "3.1.0",
        "info": {"title": "Teamarr API", "version": "9.9.9"},
        "paths": {"/health": {"get": {"operationId": "health_check_health_get", "responses": {}}}},
    }

    def handler(req: httpx2.Request):
        assert req.url.path == "/openapi.json"
        return httpx2.Response(200, json=live)

    loaded = await load_spec(Settings(), make_client(handler))
    assert isinstance(loaded, LoadedSpec)
    assert loaded.source == "live"
    assert loaded.version == "9.9.9"
    assert loaded.operation_count == 1


async def test_falls_back_to_vendored_when_unreachable(make_client):
    def handler(req):
        raise httpx2.ConnectError("boom")

    loaded = await load_spec(Settings(), make_client(handler))
    assert loaded.source == "vendored"
    assert loaded.version == "2.17.0"
    assert loaded.operation_count == 225


async def test_falls_back_to_vendored_on_non_200(make_client):
    loaded = await load_spec(Settings(), make_client(lambda r: httpx2.Response(500, text="x")))
    assert loaded.source == "vendored"


async def test_explicit_file_wins_over_live(tmp_path, make_client):
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"info": {"version": "1.2.3"}, "paths": {}}))
    calls = []

    def handler(req):
        calls.append(req.url.path)
        return httpx2.Response(200, json={})

    loaded = await load_spec(Settings(openapi_path=str(p)), make_client(handler))
    assert loaded.source == "file"
    assert loaded.version == "1.2.3"
    assert calls == []


async def test_missing_explicit_file_raises(make_client):
    with pytest.raises(FileNotFoundError):
        await load_spec(Settings(openapi_path="/nope/spec.json"), make_client(lambda r: None))
