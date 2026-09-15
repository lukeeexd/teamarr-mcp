import httpx2
from fastmcp import Client, FastMCP

from teamarr_mcp.config import Settings
from teamarr_mcp.naming import build_tool_names
from teamarr_mcp.routing import build_route_maps, component_fn, is_destructive


async def _tool_names(spec, settings) -> dict[str, str]:
    client = httpx2.AsyncClient(
        base_url="http://t",
        transport=httpx2.MockTransport(lambda r: httpx2.Response(200, json={})),
    )
    mcp = FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name="t",
        route_maps=build_route_maps(settings),
        mcp_component_fn=component_fn,
        mcp_names=build_tool_names(spec),
    )
    async with Client(mcp) as c:
        return {t.name: (t.description or "") for t in await c.list_tools()}


def test_is_destructive():
    assert is_destructive("DELETE", "/api/v1/teams/{team_id}")
    assert is_destructive("POST", "/api/v1/backup/{filename}/restore")
    assert is_destructive("POST", "/api/v1/backup")
    assert is_destructive("POST", "/api/v1/templates/restore-defaults")
    assert is_destructive("POST", "/api/v1/channels/reset")
    assert is_destructive("POST", "/api/v1/groups/cache/clear-all")
    assert is_destructive("POST", "/api/v1/groups/{group_id}/cache/clear")
    assert is_destructive("POST", "/api/v1/game-data-cache/clear")
    assert not is_destructive("POST", "/api/v1/backup/create")
    assert not is_destructive("GET", "/api/v1/teams")
    assert not is_destructive("POST", "/api/v1/channels/sync")


async def test_default_flags(vendored_spec):
    tools = await _tool_names(vendored_spec, Settings())
    for gone in (
        "download_support_bundle",
        "get_xmltv",
        "get_group_xmltv",
        "get_combined_xmltv",
        "download_backup",
        "download_specific_backup",
        "update_lifecycle_settings",
        "update_dispatcharr_settings",
        "generate_epg_stream",
    ):
        assert not any(n.startswith(gone) for n in tools), gone
    assert "update_stream_ordering_scope" in tools
    assert "delete_team" not in tools
    assert "restore_from_backup" not in tools
    assert "clear_all_match_cache" not in tools
    assert "create_team" in tools
    assert "sync_lifecycle" in tools
    assert "create_backup" in tools
    assert "list_teams" in tools


async def test_destructive_enabled(vendored_spec):
    tools = await _tool_names(vendored_spec, Settings(enable_destructive=True))
    assert "delete_team" in tools
    assert tools["delete_team"].startswith("[destructive]")
    assert "restore_from_backup" in tools
    assert not tools["list_teams"].startswith("[destructive]")


async def test_read_only(vendored_spec):
    tools = await _tool_names(vendored_spec, Settings(read_only=True, enable_destructive=True))
    assert "list_teams" in tools
    assert "create_team" not in tools
    assert "delete_team" not in tools
    assert "sync_lifecycle" not in tools


async def test_counts(vendored_spec):
    default = await _tool_names(vendored_spec, Settings())
    ro = await _tool_names(vendored_spec, Settings(read_only=True))
    full = await _tool_names(vendored_spec, Settings(enable_destructive=True))
    assert len(ro) < len(default) < len(full) <= 225
    assert len(ro) == 113 - 7  # GETs minus the 7 always-excluded GET routes
