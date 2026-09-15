import asyncio

import pytest

from teamarr_mcp import __version__, server


class FakeMcp:
    def __init__(self):
        self.calls = []
        self.run_loop = None

    async def run_async(self, **kw):
        self.calls.append(kw)
        self.run_loop = asyncio.get_running_loop()

    def run(self, **kw):  # the sync entry point must NOT be used: it starts a second loop
        raise AssertionError("main() must serve via run_async in the build loop")


async def _fake_build(settings, client=None):
    fake = FakeMcp()
    fake.build_loop = asyncio.get_running_loop()
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
    # Regression: the httpx2 client pools connections during build_server; serving from a
    # different loop made the first tool call fail with "Event loop is closed".
    assert _fake_build.last.run_loop is _fake_build.last.build_loop


def test_main_stdio(monkeypatch):
    monkeypatch.setattr(server, "build_server", _fake_build)
    monkeypatch.setenv("TEAMARR_MCP_TRANSPORT", "stdio")
    server.main([])
    assert _fake_build.last.calls == [{"transport": "stdio", "show_banner": False}]
    assert _fake_build.last.run_loop is _fake_build.last.build_loop


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as e:
        server.main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out
