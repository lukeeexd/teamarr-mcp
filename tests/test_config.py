import pytest

from teamarr_mcp.config import Settings


def test_defaults_from_empty_env():
    s = Settings.from_env({})
    assert s.url == "http://localhost:9195"
    assert s.api_key is None
    assert s.api_key_header == "X-API-Key"
    assert s.transport == "http"
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.enable_destructive is False
    assert s.read_only is False
    assert s.openapi_path is None
    assert s.log_level == "INFO"
    assert s.headers == {}


def test_all_vars_parsed_and_url_trailing_slash_stripped():
    s = Settings.from_env(
        {
            "TEAMARR_URL": "http://192.168.1.63:9195/",
            "TEAMARR_API_KEY": "abc",
            "TEAMARR_API_KEY_HEADER": "Api-Key",
            "TEAMARR_MCP_TRANSPORT": "stdio",
            "TEAMARR_MCP_HOST": "127.0.0.1",
            "TEAMARR_MCP_PORT": "9000",
            "TEAMARR_MCP_ENABLE_DESTRUCTIVE": "Yes",
            "TEAMARR_MCP_READ_ONLY": "on",
            "TEAMARR_OPENAPI_PATH": "/tmp/spec.json",
            "TEAMARR_MCP_LOG_LEVEL": "debug",
        }
    )
    assert s.url == "http://192.168.1.63:9195"
    assert s.headers == {"Api-Key": "abc"}
    assert s.transport == "stdio"
    assert s.host == "127.0.0.1"
    assert s.port == 9000
    assert s.enable_destructive is True
    assert s.read_only is True
    assert s.openapi_path == "/tmp/spec.json"
    assert s.log_level == "DEBUG"


@pytest.mark.parametrize(
    "raw,expected", [("1", True), ("TRUE", True), ("0", False), ("no", False), ("", False)]
)
def test_bool_parsing(raw, expected):
    assert Settings.from_env({"TEAMARR_MCP_READ_ONLY": raw}).read_only is expected


def test_invalid_transport_rejected():
    with pytest.raises(ValueError, match="TEAMARR_MCP_TRANSPORT"):
        Settings.from_env({"TEAMARR_MCP_TRANSPORT": "websocket"})


def test_exclude_paths_parsed():
    assert Settings.from_env({}).exclude_paths == ()
    s = Settings.from_env({"TEAMARR_MCP_EXCLUDE_PATHS": r"^/api/v1/backup, /support/ ,"})
    assert s.exclude_paths == (r"^/api/v1/backup", "/support/")
