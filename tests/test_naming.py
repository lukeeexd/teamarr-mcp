import re

from teamarr_mcp.naming import build_tool_names, strip_fastapi_suffix
from teamarr_mcp.spec import METHODS


def test_strip_suffix_simple():
    assert (
        strip_fastapi_suffix("list_teams_api_v1_teams_get", "/api/v1/teams", "get") == "list_teams"
    )


def test_strip_suffix_with_path_param():
    assert (
        strip_fastapi_suffix(
            "get_team_api_v1_teams__team_id__get", "/api/v1/teams/{team_id}", "get"
        )
        == "get_team"
    )


def test_strip_suffix_leaves_custom_ids_alone():
    assert strip_fastapi_suffix("customName", "/x", "get") == "customName"


def test_all_operations_named_uniquely(vendored_spec):
    names = build_tool_names(vendored_spec)
    op_ids = [
        op["operationId"]
        for ops in vendored_spec["paths"].values()
        for m, op in ops.items()
        if m in METHODS
    ]
    assert set(names) == set(op_ids), "every operation gets a name"
    assert len(set(names.values())) == len(names), "names are unique"
    for n in names.values():
        assert re.fullmatch(r"[a-z][a-z0-9_]*", n), n
        assert len(n) <= 56, n
        assert not re.search(r"_(get|post|put|patch|delete|\d+)$", n), n


def test_known_names(vendored_spec):
    names = build_tool_names(vendored_spec)
    assert names["list_teams_api_v1_teams_get"] == "list_teams"
    assert names["update_team_api_v1_teams__team_id__put"] == "update_team"
    assert names["update_team_api_v1_teams__team_id__patch"] == "patch_team"
    assert names["create_keyword_api_v1_keywords_post"] == "create_keyword"
    assert names["create_keyword_api_v1_detection_keywords_post"] == "create_detection_keyword"
    assert (
        names["update_api_v1_numbering_exceptions__exception_id__put"]
        == "update_numbering_exception"
    )
    assert (
        names["delete_api_v1_numbering_exceptions__exception_id__delete"]
        == "delete_numbering_exception"
    )
    assert names["get_lifecycle_settings_api_v1_settings_lifecycle_get"] == "get_lifecycle_settings"
    assert names["health_check_health_get"] == "health_check"
