import pytest

from teamarr_mcp import __version__, server


class FakeMcp:
    def __init__(self):
        self.calls = []

    def run(self, **kw):
        self.calls.append(kw)


async def _fake_build(settings, client=None):
    fake = FakeMcp()
    _fake_build.last = fake
    return fake


def test_main_http(monkeypatch):
    monkeypatch.setattr(server, "build_server", _fake_build)
    monkeypatch.setenv("TEAMARR_MCP_TRANSPORT", "http")
    monkeypatch.setenv("TEAMARR_MCP_PORT", "8123")
    server.main([])
    assert _fake_build.last.calls == [
        {"transport": "http", "host": "0.0.0.0", "port": 8123, "path": "/mcp", "show_banner": False}
    ]


def test_main_stdio(monkeypatch):
    monkeypatch.setattr(server, "build_server", _fake_build)
    monkeypatch.setenv("TEAMARR_MCP_TRANSPORT", "stdio")
    server.main([])
    assert _fake_build.last.calls == [{"transport": "stdio", "show_banner": False}]


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as e:
        server.main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out
