# teamarr-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `teamarr-mcp`, an MCP server that exposes a Teamarr instance's REST API as tools (generated from OpenAPI) plus curated tools that encode Teamarr's known API footguns, packaged for Docker, PyPI and local stdio use.

**Architecture:** `FastMCP.from_openapi()` builds the generated tier at startup from the live `/openapi.json` (vendored fallback), with a naming pass that turns FastAPI auto operationIds into clean tool names and ordered route maps that exclude noisy routes and gate destructive ones behind env flags. Curated tools are plain `@mcp.tool` functions using a thin httpx2 wrapper that converts Teamarr HTTP errors into `ToolError`s carrying the server's `detail`. One `build_server()` assembles both tiers; `main()` picks stdio or HTTP.

**Tech Stack:** Python ≥3.11, `uv`, `fastmcp>=4,<5` (which uses `httpx2`, not `httpx`), `pytest` + `pytest-asyncio`, `ruff`, hatchling, Docker (`python:3.12-slim`), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-teamarr-mcp-design.md`

## Global Constraints

- Python `>=3.11`; dependency pins `fastmcp>=4,<5`, `httpx2>=2`. Never import `httpx`; FastMCP 4's OpenAPI provider requires an `httpx2.AsyncClient`.
- Package name `teamarr_mcp`, distribution name `teamarr-mcp`, console script `teamarr-mcp`.
- All configuration via env vars named exactly as in the spec table (`TEAMARR_URL`, `TEAMARR_API_KEY`, `TEAMARR_API_KEY_HEADER`, `TEAMARR_MCP_TRANSPORT`, `TEAMARR_MCP_HOST`, `TEAMARR_MCP_PORT`, `TEAMARR_MCP_ENABLE_DESTRUCTIVE`, `TEAMARR_MCP_READ_ONLY`, `TEAMARR_OPENAPI_PATH`, `TEAMARR_MCP_LOG_LEVEL`). Booleans accept `1/true/yes/on`, case-insensitive.
- Tool names: unique, snake_case, ≤ 56 chars (FastMCP truncates at 56).
- Every tool that talks to Teamarr surfaces HTTP errors as `HTTP <status> <METHOD> <path>: <detail>`.
- Tests never hit the network unless `TEAMARR_TEST_URL` is set. Unit tests use `httpx2.MockTransport`.
- Vendored spec lives at `teamarr_mcp/specs/openapi.json` and is the copy of Teamarr v2.17.0's `/openapi.json` currently at `C:\Users\Luke\AppData\Local\Temp\claude\D--ClaudeCode-teamarr-mcp\a91616a2-fc84-4e4d-802e-3fcecf43d158\scratchpad\openapi.json` (164 paths, 225 operations).
- Live instance for opt-in tests: `http://192.168.1.63:9195` (v2.17.0). Read-only; the single write test needs the user's explicit go-ahead.
- Ruff config: `line-length = 100`, select `E, W, F, I, B, UP`, target `py311`.
- Commit after every task. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Working directory `D:\ClaudeCode\teamarr-mcp`. Run Python via `uv run`.

## Verified FastMCP 4.0.3 facts (do not re-derive)

- `FastMCP.from_openapi(openapi_spec: dict, client: httpx2.AsyncClient, name: str, route_maps: list[RouteMap], route_map_fn, mcp_component_fn, mcp_names: dict[operationId, name], tags: set[str])`.
- `from fastmcp.server.providers.openapi import RouteMap, MCPType, OpenAPITool`; `RouteMap(methods=[...] | "*", pattern=regex_str, tags=set, mcp_type=MCPType.X)`. `MCPType` ∈ `TOOL, RESOURCE, RESOURCE_TEMPLATE, EXCLUDE`. First matching map wins.
- `from fastmcp.utilities.openapi import HTTPRoute`: fields `path`, `method` (upper-case), `operation_id`, `summary`, `description`, `tags`.
- `mcp_component_fn(route: HTTPRoute, component)` mutates `component.description`, `component.tags` in place.
- Generated tools already raise `ToolError` on non-2xx with the body included, e.g. `HTTP error 400: Bad Request - {'detail': "Invalid channel_stability_mode. Valid: [...]"}`.
- `from fastmcp.exceptions import ToolError`; `from fastmcp import Client`; `async with Client(mcp) as c: tools = await c.list_tools(); r = await c.call_tool(name, args)`; `r.data` is the parsed result.
- `mcp.run(transport="stdio")`; `mcp.run(transport="http", host=..., port=..., path="/mcp", show_banner=False)`. Host/Origin protection defaults off.
- `httpx2.MockTransport(handler)` where `handler(request: httpx2.Request) -> httpx2.Response`; `httpx2.Response(status_code, json=...)`; `request.method`, `request.url.path`, `request.content` (bytes body).
- Teamarr's FastAPI operationId formula: `route.name + re.sub(r"\W", "_", path) + "_" + method.lower()`.

## File structure

```
teamarr-mcp/
  pyproject.toml            project metadata, deps, ruff, pytest
  LICENSE                   MIT
  README.md
  Dockerfile
  docker-compose.example.yml
  .dockerignore  .gitignore
  .github/workflows/ci.yml  .github/workflows/publish.yml
  scripts/refresh_spec.py   refresh vendored spec from a URL
  teamarr_mcp/
    __init__.py             __version__
    config.py               Settings dataclass + from_env
    spec.py                 LoadedSpec + load_spec (live → file → vendored)
    naming.py               build_tool_names(spec) -> {operationId: name}
    routing.py              DESTRUCTIVE / ALWAYS_EXCLUDED sets, build_route_maps, component_fn
    api.py                  TeamarrApi: httpx2 wrapper raising ToolError
    server.py               build_server(), main()
    curated/__init__.py     register_all(mcp, api, info)
    curated/info.py         teamarr_info
    curated/settings.py     update_settings
    curated/templates.py    set_template_filler
    curated/channels.py     get_event_channels_summary
    curated/matching.py     find_unmatched_streams
    curated/subscriptions.py check_tsdb_gated_subscriptions
    specs/openapi.json      vendored Teamarr 2.17.0 spec
  tests/
    conftest.py             vendored spec fixture, mock transport factory
    test_config.py test_spec.py test_naming.py test_routing.py test_api.py
    test_server.py test_curated_settings.py test_curated_templates.py
    test_curated_channels.py test_curated_matching.py test_curated_subscriptions.py
    test_main.py
    live/test_live_readonly.py   opt-in, TEAMARR_TEST_URL
```

---

### Task 1: Project scaffold and configuration

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `teamarr_mcp/__init__.py`, `teamarr_mcp/config.py`, `teamarr_mcp/specs/openapi.json`, `tests/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `teamarr_mcp.config.Settings` dataclass with fields `url: str`, `api_key: str | None`, `api_key_header: str`, `transport: str`, `host: str`, `port: int`, `enable_destructive: bool`, `read_only: bool`, `openapi_path: str | None`, `log_level: str`; classmethod `Settings.from_env(env: Mapping[str, str] | None = None) -> Settings`; property `headers -> dict[str, str]`.

- [ ] **Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "teamarr-mcp"
version = "0.1.0"
description = "MCP server for Teamarr - read and change your sports EPG config from any MCP client"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
keywords = ["mcp", "teamarr", "dispatcharr", "epg", "iptv", "sports"]
dependencies = [
    "fastmcp>=4,<5",
    "httpx2>=2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "ruff>=0.6",
]

[project.scripts]
teamarr-mcp = "teamarr_mcp.server:main"

[project.urls]
Homepage = "https://github.com/lukeeexd/teamarr-mcp"
Issues = "https://github.com/lukeeexd/teamarr-mcp/issues"

[tool.hatch.build.targets.wheel]
packages = ["teamarr_mcp"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write .gitignore, LICENSE, package init, copy vendored spec**

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
dist/
build/
*.egg-info/
.pytest_cache/
.ruff_cache/
uv.lock
```
(Note: `uv.lock` is ignored deliberately; this is a library-style package and Docker uses `pip install .`.)

`LICENSE`: standard MIT text, `Copyright (c) 2026 lukeeexd`.

`teamarr_mcp/__init__.py`:
```python
"""MCP server for Teamarr."""

__version__ = "0.1.0"
```

Copy the spec:
```bash
mkdir -p teamarr_mcp/specs
cp "C:/Users/Luke/AppData/Local/Temp/claude/D--ClaudeCode-teamarr-mcp/a91616a2-fc84-4e4d-802e-3fcecf43d158/scratchpad/openapi.json" teamarr_mcp/specs/openapi.json
```

- [ ] **Step 3: Write the failing config test**

`tests/__init__.py` empty. `tests/test_config.py`:
```python
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


@pytest.mark.parametrize("raw,expected", [("1", True), ("TRUE", True), ("0", False), ("no", False), ("", False)])
def test_bool_parsing(raw, expected):
    assert Settings.from_env({"TEAMARR_MCP_READ_ONLY": raw}).read_only is expected


def test_invalid_transport_rejected():
    with pytest.raises(ValueError, match="TEAMARR_MCP_TRANSPORT"):
        Settings.from_env({"TEAMARR_MCP_TRANSPORT": "websocket"})
```

- [ ] **Step 4: Run to verify it fails**

Run: `uv sync --extra dev && uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'teamarr_mcp.config'`. If `uv sync` fails because the `httpx2` distribution name differs, run `uv pip show httpx2` inside a venv that has fastmcp installed and use that distribution name.

- [ ] **Step 5: Implement config.py**

```python
"""Environment-driven configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}
_TRANSPORTS = {"http", "stdio"}


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE


@dataclass(frozen=True)
class Settings:
    url: str = "http://localhost:9195"
    api_key: str | None = None
    api_key_header: str = "X-API-Key"
    transport: str = "http"
    host: str = "0.0.0.0"
    port: int = 8000
    enable_destructive: bool = False
    read_only: bool = False
    openapi_path: str | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        transport = e.get("TEAMARR_MCP_TRANSPORT", "http").strip().lower()
        if transport not in _TRANSPORTS:
            raise ValueError(
                f"TEAMARR_MCP_TRANSPORT must be one of {sorted(_TRANSPORTS)}, got {transport!r}"
            )
        return cls(
            url=e.get("TEAMARR_URL", "http://localhost:9195").strip().rstrip("/"),
            api_key=e.get("TEAMARR_API_KEY") or None,
            api_key_header=e.get("TEAMARR_API_KEY_HEADER", "X-API-Key").strip(),
            transport=transport,
            host=e.get("TEAMARR_MCP_HOST", "0.0.0.0").strip(),
            port=int(e.get("TEAMARR_MCP_PORT", "8000")),
            enable_destructive=_bool(e.get("TEAMARR_MCP_ENABLE_DESTRUCTIVE")),
            read_only=_bool(e.get("TEAMARR_MCP_READ_ONLY")),
            openapi_path=e.get("TEAMARR_OPENAPI_PATH") or None,
            log_level=e.get("TEAMARR_MCP_LOG_LEVEL", "INFO").strip().upper(),
        )

    @property
    def headers(self) -> dict[str, str]:
        return {self.api_key_header: self.api_key} if self.api_key else {}
```

- [ ] **Step 6: Run tests and ruff**

Run: `uv run pytest tests/test_config.py -v && uv run ruff check .`
Expected: 8 passed, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Scaffold project and env config

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Spec loading with live → file → vendored fallback

**Files:**
- Create: `teamarr_mcp/spec.py`, `tests/conftest.py`, `tests/test_spec.py`

**Interfaces:**
- Produces: `LoadedSpec` dataclass `(spec: dict, source: Literal["live","file","vendored"], version: str, operation_count: int)`; `async def load_spec(settings: Settings, client: httpx2.AsyncClient) -> LoadedSpec`; `def load_vendored() -> dict`; `def count_operations(spec: dict) -> int`.
- Consumes: `Settings` from Task 1.

- [ ] **Step 1: Write conftest with shared fixtures**

`tests/conftest.py`:
```python
from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest

from teamarr_mcp.spec import load_vendored

Handler = Callable[[httpx2.Request], httpx2.Response]


@pytest.fixture(scope="session")
def vendored_spec() -> dict:
    return load_vendored()


@pytest.fixture
def make_client() -> Callable[[Handler], httpx2.AsyncClient]:
    def _make(handler: Handler) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(
            base_url="http://teamarr.test", transport=httpx2.MockTransport(handler)
        )

    return _make


def json_response(status: int, payload) -> httpx2.Response:
    return httpx2.Response(status, json=payload)


def body_of(request: httpx2.Request) -> dict:
    return json.loads(request.content.decode() or "{}")
```

- [ ] **Step 2: Write the failing spec tests**

`tests/test_spec.py`:
```python
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
    live = {"openapi": "3.1.0", "info": {"title": "Teamarr API", "version": "9.9.9"},
            "paths": {"/health": {"get": {"operationId": "health_check_health_get", "responses": {}}}}}

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
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_spec.py -v`
Expected: FAIL, `No module named 'teamarr_mcp.spec'`.

- [ ] **Step 4: Implement spec.py**

```python
"""Load the Teamarr OpenAPI spec: explicit file, else live instance, else vendored copy."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

import httpx2

from teamarr_mcp.config import Settings

log = logging.getLogger(__name__)

METHODS = ("get", "post", "put", "patch", "delete")


def count_operations(spec: dict) -> int:
    return sum(1 for ops in spec.get("paths", {}).values() for m in ops if m in METHODS)


def load_vendored() -> dict:
    text = resources.files("teamarr_mcp").joinpath("specs/openapi.json").read_text("utf-8")
    return json.loads(text)


@dataclass(frozen=True)
class LoadedSpec:
    spec: dict
    source: Literal["live", "file", "vendored"]
    version: str
    operation_count: int

    @classmethod
    def build(cls, spec: dict, source) -> LoadedSpec:
        return cls(
            spec=spec,
            source=source,
            version=str(spec.get("info", {}).get("version", "unknown")),
            operation_count=count_operations(spec),
        )


async def load_spec(settings: Settings, client: httpx2.AsyncClient) -> LoadedSpec:
    if settings.openapi_path:
        path = Path(settings.openapi_path)
        if not path.is_file():
            raise FileNotFoundError(f"TEAMARR_OPENAPI_PATH not found: {path}")
        return LoadedSpec.build(json.loads(path.read_text("utf-8")), "file")

    try:
        resp = await client.get("/openapi.json", timeout=10.0)
        if resp.status_code == 200:
            return LoadedSpec.build(resp.json(), "live")
        log.warning("Teamarr returned HTTP %s for /openapi.json; using vendored spec",
                    resp.status_code)
    except httpx2.HTTPError as exc:
        log.warning("Could not fetch %s/openapi.json (%s); using vendored spec",
                    settings.url, exc)
    return LoadedSpec.build(load_vendored(), "vendored")
```

- [ ] **Step 5: Run tests and ruff**

Run: `uv run pytest tests/test_spec.py -v && uv run ruff check .`
Expected: 6 passed. If `resources.files(...).joinpath("specs/openapi.json")` fails because hatch excluded the JSON, add `[tool.hatch.build] include = ["teamarr_mcp/**/*.py", "teamarr_mcp/specs/*.json"]` to pyproject.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Load OpenAPI spec from file, live instance or vendored copy

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Tool naming from FastAPI operationIds

**Files:**
- Create: `teamarr_mcp/naming.py`, `tests/test_naming.py`

**Interfaces:**
- Produces: `def build_tool_names(spec: dict) -> dict[str, str]` mapping operationId → tool name; `OVERRIDES: dict[tuple[str, str], str]` keyed `(METHOD, path)`; `def strip_fastapi_suffix(operation_id: str, path: str, method: str) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_naming.py`:
```python
import re

from teamarr_mcp.naming import build_tool_names, strip_fastapi_suffix
from teamarr_mcp.spec import METHODS


def test_strip_suffix_simple():
    assert strip_fastapi_suffix("list_teams_api_v1_teams_get", "/api/v1/teams", "get") == "list_teams"


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


def test_known_names(vendored_spec):
    names = build_tool_names(vendored_spec)
    assert names["list_teams_api_v1_teams_get"] == "list_teams"
    assert names["update_team_api_v1_teams__team_id__put"] == "update_team"
    assert names["update_team_api_v1_teams__team_id__patch"] == "patch_team"
    assert names["create_keyword_api_v1_keywords_post"] == "create_keyword"
    assert names["create_keyword_api_v1_detection_keywords_post"] == "create_detection_keyword"
    assert names["update_api_v1_numbering_exceptions__exception_id__put"] == "update_numbering_exception"
    assert names["delete_api_v1_numbering_exceptions__exception_id__delete"] == "delete_numbering_exception"
    assert names["get_lifecycle_settings_api_v1_settings_lifecycle_get"] == "get_lifecycle_settings"
    assert names["health_check_health_get"] == "health_check"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_naming.py -v`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement naming.py**

```python
"""Turn FastAPI's auto-generated operationIds into short, unique tool names."""

from __future__ import annotations

import re
from collections import Counter

from teamarr_mcp.spec import METHODS

# (METHOD, path) -> desired tool name. Resolves collisions after suffix stripping.
OVERRIDES: dict[tuple[str, str], str] = {
    ("PATCH", "/api/v1/teams/{team_id}"): "patch_team",
    ("POST", "/api/v1/detection-keywords"): "create_detection_keyword",
    ("PUT", "/api/v1/detection-keywords/id/{keyword_id}"): "update_detection_keyword",
    ("DELETE", "/api/v1/detection-keywords/id/{keyword_id}"): "delete_detection_keyword",
    ("PUT", "/api/v1/numbering-exceptions/{exception_id}"): "update_numbering_exception",
    ("DELETE", "/api/v1/numbering-exceptions/{exception_id}"): "delete_numbering_exception",
}


def fastapi_suffix(path: str, method: str) -> str:
    return re.sub(r"\W", "_", path) + "_" + method.lower()


def strip_fastapi_suffix(operation_id: str, path: str, method: str) -> str:
    suffix = fastapi_suffix(path, method)
    if operation_id.endswith(suffix):
        return operation_id[: -len(suffix)]
    return operation_id


def _slug(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_").lower()
    name = re.sub(r"_+", "_", name)
    return name[:56] or "op"


def build_tool_names(spec: dict) -> dict[str, str]:
    routes: list[tuple[str, str, str]] = []  # (operationId, path, METHOD)
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            if method in METHODS and "operationId" in op:
                routes.append((op["operationId"], path, method.upper()))

    proposed: dict[str, str] = {}
    for op_id, path, method in routes:
        override = OVERRIDES.get((method, path))
        proposed[op_id] = _slug(override or strip_fastapi_suffix(op_id, path, method.lower()))

    counts = Counter(proposed.values())
    names: dict[str, str] = {}
    for op_id, path, method in routes:
        name = proposed[op_id]
        if counts[name] > 1 and (method, path) not in OVERRIDES:
            name = _slug(f"{name}_{method.lower()}")
        names[op_id] = name

    # Last resort for drift: number any remaining duplicates deterministically.
    seen: Counter[str] = Counter()
    final: dict[str, str] = {}
    for op_id, _, _ in routes:
        name = names[op_id]
        seen[name] += 1
        final[op_id] = name if seen[name] == 1 else _slug(f"{name}_{seen[name]}")
    return final
```

- [ ] **Step 4: Run tests; add overrides for any collision the test reveals**

Run: `uv run pytest tests/test_naming.py -v`
Expected: PASS. If `test_all_operations_named_uniquely` or `test_known_names` fails, print the offenders with:
```bash
uv run python -c "from teamarr_mcp.naming import build_tool_names; from teamarr_mcp.spec import load_vendored; from collections import Counter; n=build_tool_names(load_vendored()); c=Counter(n.values()); print({k:v for k,v in n.items() if c[v]>1 or v.endswith(('_put','_post','_get','_delete','_patch','_2'))})"
```
and add `OVERRIDES` rows so no name ends in a bare method or `_2`. Re-run until green.

- [ ] **Step 5: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Derive clean unique tool names from FastAPI operationIds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Route maps, destructive gating and descriptions

**Files:**
- Create: `teamarr_mcp/routing.py`, `tests/test_routing.py`

**Interfaces:**
- Produces: `ALWAYS_EXCLUDED: list[tuple[str, str]]` of `(METHOD_or_*, regex)`; `DESTRUCTIVE: list[tuple[str, str]]`; `def is_destructive(method: str, path: str) -> bool`; `def build_route_maps(settings: Settings) -> list[RouteMap]`; `def component_fn(route: HTTPRoute, component) -> None`.
- Consumes: `Settings`.

- [ ] **Step 1: Write the failing tests**

`tests/test_routing.py`:
```python
import httpx2
from fastmcp import Client, FastMCP

from teamarr_mcp.config import Settings
from teamarr_mcp.naming import build_tool_names
from teamarr_mcp.routing import build_route_maps, component_fn, is_destructive


async def _tool_names(spec, settings) -> dict[str, str]:
    client = httpx2.AsyncClient(base_url="http://t", transport=httpx2.MockTransport(
        lambda r: httpx2.Response(200, json={})))
    mcp = FastMCP.from_openapi(
        openapi_spec=spec, client=client, name="t",
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
    # excluded always
    for gone in ("get_support_bundle", "get_xmltv", "download_backup", "update_lifecycle_settings",
                 "update_dispatcharr_settings", "generate_epg_stream"):
        assert not any(n.startswith(gone) for n in tools), gone
    # settings scope PUT is per-item, stays
    assert "update_stream_ordering_scope" in tools
    # destructive gated off
    assert "delete_team" not in tools
    assert "restore_from_backup" not in tools
    assert "clear_all_match_cache" not in tools
    # normal writes remain
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
    assert len(ro) == 113 - 6  # GETs minus the 6 always-excluded GET routes
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_routing.py -v`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement routing.py**

```python
"""Ordered route maps: always-excluded, read-only gate, destructive gate, then tools."""

from __future__ import annotations

import re

from fastmcp.server.providers.openapi import MCPType, RouteMap
from fastmcp.utilities.openapi import HTTPRoute

from teamarr_mcp.config import Settings

# (METHOD or "*", anchored regex on path)
ALWAYS_EXCLUDED: list[tuple[str, str]] = [
    ("GET", r"^/api/v1/support/bundle$"),          # large archive
    ("GET", r"^/api/v1/backup/file/[^/]+$"),        # binary download
    ("GET", r"^/api/v1/epg/xmltv$"),                # whole XMLTV document
    ("GET", r"^/api/v1/groups/[^/]+/xmltv$"),
    ("GET", r"^/api/v1/groups/xmltv/combined$"),
    ("GET", r"^/api/v1/epg/generate/stream$"),      # SSE stream
    # Whole-block settings PUTs are replaced by the curated update_settings tool.
    ("PUT", r"^/api/v1/settings/(?!stream-ordering/scopes/)[^/]+(/[^/]+)*$"),
]

DESTRUCTIVE: list[tuple[str, str]] = [
    ("DELETE", r".*"),
    ("POST", r"^/api/v1/backup$"),
    ("POST", r"^/api/v1/backup/[^/]+/restore$"),
    ("POST", r"^/api/v1/templates/restore-defaults$"),
    ("POST", r"^/api/v1/channels/reset$"),
    ("POST", r"^/api/v1/groups/cache/clear(-all)?$"),
    ("POST", r"^/api/v1/groups/[^/]+/cache/clear$"),
    ("POST", r"^/api/v1/game-data-cache/clear$"),
]


def _matches(rules: list[tuple[str, str]], method: str, path: str) -> bool:
    return any(
        (m == "*" or m == method.upper()) and re.search(pattern, path)
        for m, pattern in rules
    )


def is_destructive(method: str, path: str) -> bool:
    return _matches(DESTRUCTIVE, method, path)


def _maps(rules: list[tuple[str, str]], mcp_type: MCPType) -> list[RouteMap]:
    return [
        RouteMap(methods="*" if m == "*" else [m], pattern=p, mcp_type=mcp_type)
        for m, p in rules
    ]


def build_route_maps(settings: Settings) -> list[RouteMap]:
    maps = _maps(ALWAYS_EXCLUDED, MCPType.EXCLUDE)
    if settings.read_only:
        maps.append(
            RouteMap(methods=["POST", "PUT", "PATCH", "DELETE"], pattern=r".*",
                     mcp_type=MCPType.EXCLUDE)
        )
    if not settings.enable_destructive:
        maps += _maps(DESTRUCTIVE, MCPType.EXCLUDE)
    maps.append(RouteMap(mcp_type=MCPType.TOOL))
    return maps


def component_fn(route: HTTPRoute, component) -> None:
    """Tag components and flag destructive ones in the description."""
    component.tags.add("teamarr")
    component.tags.add("read" if route.method.upper() == "GET" else "write")
    if is_destructive(route.method, route.path):
        component.tags.add("destructive")
        component.description = "[destructive] " + (component.description or "")
```

- [ ] **Step 4: Run tests; fix counts**

Run: `uv run pytest tests/test_routing.py -v`
Expected: PASS. If `test_counts` fails on the read-only number, recount the always-excluded GET routes in the vendored spec (`support/bundle`, `backup/file/{f}`, `epg/xmltv`, `groups/{id}/xmltv`, `groups/xmltv/combined`, `epg/generate/stream`) and correct the assertion to match. Do not loosen the other assertions.

- [ ] **Step 5: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Add route maps with read-only and destructive gating

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Teamarr API wrapper for curated tools

**Files:**
- Create: `teamarr_mcp/api.py`, `tests/test_api.py`

**Interfaces:**
- Produces: `class TeamarrApi` with `__init__(self, client: httpx2.AsyncClient, base_url: str)`, `async get(path, params=None) -> Any`, `async put(path, json) -> Any`, `async post(path, json=None) -> Any`, `async request(method, path, *, params=None, json=None) -> Any`; raises `ToolError` formatted `HTTP <status> <METHOD> <path>: <detail>` or `Cannot reach Teamarr at <base_url>: <error>`.
- Produces: `def format_detail(payload) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_api.py`:
```python
import httpx2
import pytest
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi, format_detail
from tests.conftest import body_of


def test_format_detail_string_and_json():
    assert format_detail({"detail": "Invalid x. Valid: ['a']"}) == "Invalid x. Valid: ['a']"
    assert format_detail({"detail": [{"loc": ["body", "x"], "msg": "bad"}]}) == \
        '[{"loc": ["body", "x"], "msg": "bad"}]'
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
    api = TeamarrApi(make_client(lambda r: httpx2.Response(
        400, json={"detail": "Invalid channel_stability_mode. Valid: ['compact']"})), "http://t")
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_api.py -v` → FAIL, module not found.

- [ ] **Step 3: Implement api.py**

```python
"""Thin async wrapper over httpx2 that turns Teamarr errors into ToolErrors."""

from __future__ import annotations

import json
from typing import Any

import httpx2
from fastmcp.exceptions import ToolError


def format_detail(payload: Any) -> str:
    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
        return detail if isinstance(detail, str) else json.dumps(detail)
    if isinstance(payload, str):
        return payload
    return json.dumps(payload)


class TeamarrApi:
    def __init__(self, client: httpx2.AsyncClient, base_url: str) -> None:
        self._client = client
        self.base_url = base_url

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        try:
            resp = await self._client.request(method, path, params=params, json=json)
        except httpx2.HTTPError as exc:
            raise ToolError(f"Cannot reach Teamarr at {self.base_url}: {exc}") from exc
        if resp.status_code >= 400:
            try:
                payload: Any = resp.json()
            except ValueError:
                payload = resp.text
            raise ToolError(f"HTTP {resp.status_code} {method.upper()} {path}: {format_detail(payload)}")
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def put(self, path: str, json: Any) -> Any:
        return await self.request("PUT", path, json=json)

    async def post(self, path: str, json: Any = None) -> Any:
        return await self.request("POST", path, json=json)
```

- [ ] **Step 4: Run tests and ruff**

Run: `uv run pytest tests/test_api.py -v && uv run ruff check .` → 6 passed. Ruff may flag the `json` parameter shadowing the module inside `request`; the implementation uses `resp.json()` (method) and module-level `json.dumps` only in `format_detail`, so it is safe, but if `F811`/`A002` fires, rename the parameter to `body` in all four methods and in the tests' call sites (`json=` → `body=`).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Add TeamarrApi wrapper with ToolError mapping

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Server assembly and `teamarr_info`

**Files:**
- Create: `teamarr_mcp/server.py` (build only; `main()` in Task 12), `teamarr_mcp/curated/__init__.py`, `teamarr_mcp/curated/info.py`, `tests/test_server.py`

**Interfaces:**
- Produces: `async def build_server(settings: Settings, client: httpx2.AsyncClient | None = None) -> FastMCP`; module `teamarr_mcp.curated` exposes `def register_all(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None`; `@dataclass ServerContext(settings: Settings, loaded: LoadedSpec, generated_tool_count: int)`. Each curated module exposes `def register(mcp, api, ctx) -> None`.
- Produces tool `teamarr_info() -> dict` with keys `teamarr_url, teamarr_version, health, spec_source, spec_version, generated_tools, curated_tools, read_only, destructive_enabled`.

- [ ] **Step 1: Write the failing test**

`tests/test_server.py`:
```python
import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server


def _handler(r: httpx2.Request):
    if r.url.path == "/openapi.json":
        raise httpx2.ConnectError("offline")  # force vendored
    if r.url.path == "/health":
        return httpx2.Response(200, json={"status": "healthy", "version": "2.17.0"})
    return httpx2.Response(200, json={})


async def test_build_server_has_generated_and_curated_tools(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler))
    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
    assert "list_teams" in names
    assert "teamarr_info" in names
    assert "update_lifecycle_settings" not in names


async def test_teamarr_info(make_client):
    mcp = await build_server(Settings(url="http://t", read_only=True), client=make_client(_handler))
    async with Client(mcp) as c:
        info = (await c.call_tool("teamarr_info", {})).data
    assert info["teamarr_url"] == "http://t"
    assert info["teamarr_version"] == "2.17.0"
    assert info["health"]["status"] == "healthy"
    assert info["spec_source"] == "vendored"
    assert info["spec_version"] == "2.17.0"
    assert info["read_only"] is True
    assert info["destructive_enabled"] is False
    assert info["generated_tools"] > 100
    assert info["curated_tools"] >= 1
```

- [ ] **Step 2: Run to verify failure** → `uv run pytest tests/test_server.py -v` FAIL.

- [ ] **Step 3: Implement curated/__init__.py and curated/info.py**

`teamarr_mcp/curated/__init__.py`:
```python
"""Hand-written tools that encode Teamarr API footguns."""

from __future__ import annotations

from dataclasses import dataclass

from fastmcp import FastMCP

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.config import Settings
from teamarr_mcp.spec import LoadedSpec


@dataclass
class ServerContext:
    settings: Settings
    loaded: LoadedSpec
    generated_tool_count: int
    curated_tool_names: list[str]


def register_all(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    from teamarr_mcp.curated import info

    for module in (info,):
        module.register(mcp, api, ctx)
```
(Later tasks append modules to that tuple.)

`teamarr_mcp/curated/info.py`:
```python
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    @mcp.tool(tags={"teamarr", "read"})
    async def teamarr_info() -> dict:
        """Report the connected Teamarr instance, its version, and how this MCP server
        is configured (spec source, tool counts, read-only / destructive flags).
        Call this first if a tool you expected is missing."""
        try:
            health = await api.get("/health")
        except ToolError as exc:
            health = {"status": "unreachable", "error": str(exc)}
        return {
            "teamarr_url": ctx.settings.url,
            "teamarr_version": health.get("version") if isinstance(health, dict) else None,
            "health": health,
            "spec_source": ctx.loaded.source,
            "spec_version": ctx.loaded.version,
            "generated_tools": ctx.generated_tool_count,
            "curated_tools": len(ctx.curated_tool_names),
            "read_only": ctx.settings.read_only,
            "destructive_enabled": ctx.settings.enable_destructive,
        }

    ctx.curated_tool_names.append("teamarr_info")
```

- [ ] **Step 4: Implement server.py (build only)**

```python
"""Assemble the generated and curated tiers into one FastMCP server."""

from __future__ import annotations

import logging

import httpx2
from fastmcp import FastMCP

from teamarr_mcp import __version__
from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.config import Settings
from teamarr_mcp.curated import ServerContext, register_all
from teamarr_mcp.naming import build_tool_names
from teamarr_mcp.routing import build_route_maps, component_fn
from teamarr_mcp.spec import load_spec

log = logging.getLogger(__name__)

INSTRUCTIONS = """Tools for a Teamarr sports-EPG instance. Prefer `update_settings` over any
raw settings PUT: Teamarr replaces whole settings blocks on PUT. Destructive tools are hidden
unless TEAMARR_MCP_ENABLE_DESTRUCTIVE is set. Call `teamarr_info` to see the configuration."""


def make_client(settings: Settings) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(base_url=settings.url, headers=settings.headers, timeout=60.0)


async def build_server(settings: Settings, client: httpx2.AsyncClient | None = None) -> FastMCP:
    client = client or make_client(settings)
    loaded = await load_spec(settings, client)
    log.info("Using %s OpenAPI spec (Teamarr %s, %d operations)",
             loaded.source, loaded.version, loaded.operation_count)

    mcp = FastMCP.from_openapi(
        openapi_spec=loaded.spec,
        client=client,
        name="teamarr",
        version=__version__,
        instructions=INSTRUCTIONS,
        route_maps=build_route_maps(settings),
        mcp_component_fn=component_fn,
        mcp_names=build_tool_names(loaded.spec),
    )
    generated = len(await mcp.get_tools())
    ctx = ServerContext(settings=settings, loaded=loaded, generated_tool_count=generated,
                        curated_tool_names=[])
    register_all(mcp, TeamarrApi(client, settings.url), ctx)
    log.info("Registered %d generated + %d curated tools", generated, len(ctx.curated_tool_names))
    return mcp
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS. If `mcp.get_tools()` does not exist or is not awaitable in this FastMCP build, replace with `len(await mcp.list_tools())` or, failing both, `len([t async for t in ...])`; check with `uv run python -c "from fastmcp import FastMCP; print([m for m in dir(FastMCP) if 'tool' in m])"`. If `version=`/`instructions=` are rejected by `from_openapi(**settings)`, drop `version` and keep `instructions`.

- [ ] **Step 6: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Assemble server and add teamarr_info tool

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `update_settings` read-merge-write

**Files:**
- Create: `teamarr_mcp/curated/settings.py`, `tests/test_curated_settings.py`
- Modify: `teamarr_mcp/curated/__init__.py` (add `settings` to the module tuple)

**Interfaces:**
- Produces tool `update_settings(block: str, changes: dict, replace: bool = False) -> dict`; helper `def merge_block(current: dict, changes: dict) -> dict` (pure); `MASK = "********"`; `def settings_blocks(spec: dict) -> list[str]` (blocks with both GET and PUT under `/api/v1/settings/<block>`).

- [ ] **Step 1: Write the failing tests**

`tests/test_curated_settings.py`:
```python
import httpx2
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from teamarr_mcp.config import Settings
from teamarr_mcp.curated.settings import merge_block, settings_blocks
from teamarr_mcp.server import build_server
from tests.conftest import body_of

LIFECYCLE = {"channel_create_timing": "before_event", "channel_delete_timing": "after_event",
             "channel_pre_buffer_minutes": 1440, "channel_post_buffer_minutes": 120,
             "channel_range_start": 2000, "channel_range_end": None}
DISPATCHARR = {"enabled": True, "url": "http://d:9191", "username": "Luke",
               "password": "********", "epg_id": 24, "default_channel_profile_ids": [1],
               "default_stream_profile_id": None, "default_channel_group_id": 652,
               "default_channel_group_mode": "Events | {sport}", "cleanup_unused_logos": True}


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
            return httpx2.Response(400, json={"detail": "Invalid channel_stability_mode. Valid: ['compact', 'gap', 'strict']"})
        if r.url.path == "/api/v1/settings/channel-numbering":
            return httpx2.Response(200, json={"channel_stability_mode": "compact"})
        return httpx2.Response(200, json={})
    return handler


async def test_update_settings_merges_then_puts(make_client):
    store, calls = dict(LIFECYCLE), []
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler_factory(store, calls)))
    async with Client(mcp) as c:
        result = (await c.call_tool("update_settings", {
            "block": "lifecycle", "changes": {"channel_post_buffer_minutes": 180}})).data
    put = [c for c in calls if c[0] == "PUT"][0]
    assert put[2]["channel_range_start"] == 2000
    assert put[2]["channel_post_buffer_minutes"] == 180
    assert result["channel_post_buffer_minutes"] == 180


async def test_update_settings_replace_sends_changes_verbatim(make_client):
    store, calls = dict(LIFECYCLE), []
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler_factory(store, calls)))
    async with Client(mcp) as c:
        await c.call_tool("update_settings", {"block": "lifecycle",
                                              "changes": {"channel_range_start": 3000}, "replace": True})
    assert [c for c in calls if c[0] == "GET" and "lifecycle" in c[1]] == []
    assert [c for c in calls if c[0] == "PUT"][0][2] == {"channel_range_start": 3000}


async def test_update_settings_surfaces_enum_error(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler_factory({}, [])))
    async with Client(mcp) as c:
        with pytest.raises(ToolError, match=r"Valid: \['compact', 'gap', 'strict'\]"):
            await c.call_tool("update_settings", {"block": "channel-numbering",
                                                  "changes": {"channel_stability_mode": "bogus"}})


async def test_update_settings_unknown_block(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler_factory({}, [])))
    async with Client(mcp) as c:
        with pytest.raises(ToolError, match="Unknown settings block 'nope'"):
            await c.call_tool("update_settings", {"block": "nope", "changes": {}})


async def test_update_settings_hidden_in_read_only(make_client):
    mcp = await build_server(Settings(url="http://t", read_only=True), client=make_client(_handler_factory({}, [])))
    async with Client(mcp) as c:
        assert "update_settings" not in {t.name for t in await c.list_tools()}
```

- [ ] **Step 2: Run to verify failure** → `uv run pytest tests/test_curated_settings.py -v` FAIL.

- [ ] **Step 3: Implement curated/settings.py**

```python
from __future__ import annotations

import re

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext

MASK = "********"
_BLOCK_RE = re.compile(r"^/api/v1/settings/([^/{}]+)$")


def settings_blocks(spec: dict) -> list[str]:
    blocks = []
    for path, ops in spec.get("paths", {}).items():
        m = _BLOCK_RE.match(path)
        if m and "get" in ops and "put" in ops:
            blocks.append(m.group(1))
    return sorted(blocks)


def merge_block(current: dict, changes: dict) -> dict:
    merged = {k: v for k, v in current.items() if v != MASK}
    merged.update(changes)
    return merged


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    if ctx.settings.read_only:
        return
    blocks = settings_blocks(ctx.loaded.spec)

    @mcp.tool(tags={"teamarr", "write"})
    async def update_settings(block: str, changes: dict, replace: bool = False) -> dict:
        """Safely change fields in a Teamarr settings block.

        Teamarr's PUT /api/v1/settings/<block> replaces the WHOLE block: any field you omit
        is reset to its default (e.g. `channel_range_start` on `lifecycle`, `epg_id` /
        `default_channel_group_id` on `dispatcharr`). This tool GETs the block, merges your
        `changes` over it, and PUTs the result. Masked secrets (`********`) are dropped so the
        server keeps the stored value. Set `replace=True` to PUT `changes` verbatim.

        Blocks available on this instance: BLOCKS. Invalid enum values return Teamarr's 400
        message listing the valid options.
        """
        if block not in blocks:
            raise ToolError(f"Unknown settings block '{block}'. Available: {', '.join(blocks)}")
        path = f"/api/v1/settings/{block}"
        payload = changes if replace else merge_block(await api.get(path), changes)
        return await api.put(path, json=payload)

    update_settings.description = update_settings.description.replace("BLOCKS", ", ".join(blocks))
    ctx.curated_tool_names.append("update_settings")
```

Then in `curated/__init__.py` change the import and tuple to `from teamarr_mcp.curated import info, settings` and `for module in (info, settings):`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_curated_settings.py -v`
Expected: PASS. If `update_settings.description` is not assignable (the decorator returns a `FunctionTool`), instead build the docstring before decorating: define the function inside `register`, set `fn.__doc__ = fn.__doc__.replace("BLOCKS", ...)`, then call `mcp.tool(fn, tags=...)`.

- [ ] **Step 5: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Add update_settings read-merge-write tool

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: `set_template_filler`

**Files:**
- Create: `teamarr_mcp/curated/templates.py`, `tests/test_curated_templates.py`
- Modify: `teamarr_mcp/curated/__init__.py` (add `templates`)

**Interfaces:**
- Produces tool `set_template_filler(section: Literal["pregame","postgame"], field: Literal["title","subtitle","description","description_fallback","art_url"], text: str, template_ids: list[int] | None = None, template_type: str | None = "event") -> dict` returning `{"changed": [ids], "unchanged": [ids], "skipped": [{"id", "reason"}], "failed": [{"id", "error"}]}`.
- Helper `def update_body(full: dict, spec: dict) -> dict` keeps only keys in the spec's `TemplateUpdate.properties` (fallback: a hard-coded list of those 28 keys).

Teamarr facts: `GET /api/v1/templates` → `{"templates": [...summary...]}` or a bare list (handle both); `GET /api/v1/templates/{id}` → `TemplateFullResponse` with `pregame_fallback` / `postgame_fallback` dicts holding those five keys; `PUT /api/v1/templates/{id}` body `TemplateUpdate`. `template_type` is `"event"` or `"team"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_curated_templates.py`:
```python
import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.curated.templates import UPDATE_KEYS_FALLBACK, update_body
from teamarr_mcp.server import build_server
from tests.conftest import body_of


def _full(i, ttype, post_title="Postgame"):
    return {"id": i, "name": f"T{i}", "template_type": ttype, "created_at": "x", "updated_at": "y",
            "team_count": 0, "global_assignments": None, "title_format": "{gracenote_category}",
            "pregame_fallback": {"title": "Coming up", "subtitle": "", "description": "",
                                 "description_fallback": "", "art_url": ""},
            "postgame_fallback": {"title": post_title, "subtitle": "", "description": "",
                                  "art_url": ""}}


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
            return httpx2.Response(200, json={"templates": [
                {"id": t["id"], "name": t["name"], "template_type": t["template_type"]}
                for t in templates.values()]})
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
    templates = {1: _full(1, "team"), 2: _full(2, "event"), 3: _full(3, "event", "New text"),
                 4: _full(4, "event")}
    puts = []
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler_factory(templates, puts)))
    async with Client(mcp) as c:
        res = (await c.call_tool("set_template_filler", {
            "section": "postgame", "field": "title", "text": "New text"})).data
    assert res["changed"] == [2]
    assert res["unchanged"] == [3]
    assert res["skipped"] == [{"id": 1, "reason": "template_type=team"}]
    assert res["failed"][0]["id"] == 4 and "bad template" in res["failed"][0]["error"]
    put_ids = [p[0] for p in puts]
    assert put_ids == [2, 4]
    assert puts[0][1]["postgame_fallback"]["title"] == "New text"
    assert puts[0][1]["postgame_fallback"]["subtitle"] == ""   # other keys preserved
    assert "id" not in puts[0][1]


async def test_explicit_ids_bypass_type_filter(make_client):
    templates = {1: _full(1, "team"), 2: _full(2, "event")}
    puts = []
    mcp = await build_server(Settings(url="http://t"), client=make_client(_handler_factory(templates, puts)))
    async with Client(mcp) as c:
        res = (await c.call_tool("set_template_filler", {
            "section": "pregame", "field": "description", "text": "{relative_day_title}",
            "template_ids": [1]})).data
    assert res["changed"] == [1] and res["skipped"] == []
    assert puts[0][1]["pregame_fallback"]["description"] == "{relative_day_title}"
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement curated/templates.py**

```python
from __future__ import annotations

from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext

UPDATE_KEYS_FALLBACK = [
    "name", "sport", "league", "title_format", "subtitle_template", "description_template",
    "program_art_url", "game_duration_mode", "game_duration_override", "xmltv_flags",
    "xmltv_video", "xmltv_categories", "xmltv_filler_categories", "pregame_enabled",
    "pregame_fallback", "postgame_enabled", "postgame_fallback", "postgame_conditional",
    "idle_enabled", "idle_content", "idle_conditional", "idle_offseason",
    "pregame_conditional_rows", "postgame_conditional_rows", "idle_conditional_rows",
    "conditional_descriptions", "event_channel_name", "event_channel_logo_url",
]

Section = Literal["pregame", "postgame"]
Field = Literal["title", "subtitle", "description", "description_fallback", "art_url"]


def update_keys(spec: dict) -> list[str]:
    props = spec.get("components", {}).get("schemas", {}).get("TemplateUpdate", {}).get("properties")
    return list(props) if props else UPDATE_KEYS_FALLBACK


def update_body(full: dict, spec: dict) -> dict:
    keys = update_keys(spec)
    return {k: v for k, v in full.items() if k in keys}


def _as_list(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    return payload.get("templates", [])


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    if ctx.settings.read_only:
        return
    spec = ctx.loaded.spec

    @mcp.tool(tags={"teamarr", "write"})
    async def set_template_filler(
        section: Section,
        field: Field,
        text: str,
        template_ids: list[int] | None = None,
        template_type: str | None = "event",
    ) -> dict:
        """Set one pregame/postgame filler field across many templates in one call.

        Edits `<section>_fallback.<field>` on every template of `template_type` (default
        `event`; pass null for all types) or on the explicit `template_ids` (type filter
        ignored). Each template is fetched in full and PUT back with only that field changed,
        so nothing else is lost. Useful variables: `{relative_day_title}` / `{relative_day}`
        (Today / Tomorrow / weekday) rather than `{game_day}`, which is always the weekday name.
        Returns changed / unchanged / skipped / failed ids.
        """
        summaries = _as_list(await api.get("/api/v1/templates"))
        if template_ids is not None:
            chosen = [{"id": i} for i in template_ids]
        else:
            chosen = summaries
        result: dict = {"changed": [], "unchanged": [], "skipped": [], "failed": []}
        by_id = {s["id"]: s for s in summaries}
        for s in chosen:
            tid = s["id"]
            ttype = by_id.get(tid, s).get("template_type")
            if template_ids is None and template_type and ttype != template_type:
                result["skipped"].append({"id": tid, "reason": f"template_type={ttype}"})
                continue
            try:
                full = await api.get(f"/api/v1/templates/{tid}")
                block = dict(full.get(f"{section}_fallback") or {})
                if block.get(field) == text:
                    result["unchanged"].append(tid)
                    continue
                block[field] = text
                body = update_body(full, spec)
                body[f"{section}_fallback"] = block
                await api.put(f"/api/v1/templates/{tid}", json=body)
                result["changed"].append(tid)
            except ToolError as exc:
                result["failed"].append({"id": tid, "error": str(exc)})
        return result

    ctx.curated_tool_names.append("set_template_filler")
```

Add `templates` to the module tuple in `curated/__init__.py`.

- [ ] **Step 4: Run tests** → `uv run pytest tests/test_curated_templates.py -v` PASS.

- [ ] **Step 5: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Add set_template_filler bulk edit tool

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: `get_event_channels_summary`

**Files:**
- Create: `teamarr_mcp/curated/channels.py`, `tests/test_curated_channels.py`
- Modify: `teamarr_mcp/curated/__init__.py` (add `channels`)

**Interfaces:**
- Produces tool `get_event_channels_summary(include_deleted: bool = False) -> dict` → `{"count": int, "channels": [ {channel_number, channel_name, event_name, event_date, sport, league, sync_status, group_id, group_name, group_stream_count, template_id, template_name, dispatcharr_channel_id, tvg_id} ]}` sorted by `channel_number`.

Teamarr facts: `GET /api/v1/channels/managed?include_deleted=` → `{"channels": [...], "total": n}` with keys `id, channel_number, channel_name, event_name, event_date, sport, league, sync_status, event_epg_group_id, dispatcharr_channel_id, tvg_id, deleted_at`. `GET /api/v1/groups` → `{"groups": [...], "total": n}` with `id, name, display_name, stream_count, matched_count, leagues, enabled`. Groups do not expose a template id; templates are assigned via `global_assignments` (`leagues` lists) on `GET /api/v1/templates`. Resolve template by first event template whose `global_assignments[*].leagues` contains the channel's `league`, else whose `sports` contains the channel's `sport`, else `None`.

- [ ] **Step 1: Write the failing test**

`tests/test_curated_channels.py`:
```python
import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server

CHANNELS = {"channels": [
    {"id": 1, "channel_number": 2003, "channel_name": "MLB 03 | A at B", "event_name": "A at B",
     "event_date": "2026-09-15 18:40", "sport": "baseball", "league": "mlb", "sync_status": "synced",
     "event_epg_group_id": 7, "dispatcharr_channel_id": 900, "tvg_id": "teamarr-event-1-x", "deleted_at": None},
    {"id": 2, "channel_number": 2001, "channel_name": "UFC", "event_name": "Fight", "event_date": "x",
     "sport": "mma", "league": "ufc", "sync_status": "pending", "event_epg_group_id": 99,
     "dispatcharr_channel_id": None, "tvg_id": "t2", "deleted_at": None},
], "total": 2}
GROUPS = {"groups": [{"id": 7, "name": "USA | MLB", "display_name": "MLB", "stream_count": 30}], "total": 1}
TEMPLATES = {"templates": [
    {"id": 5, "name": "College", "template_type": "event", "global_assignments": [{"sports": None, "leagues": ["ncaaf"]}]},
    {"id": 6, "name": "Baseball", "template_type": "event", "global_assignments": [{"sports": ["baseball"], "leagues": None}]},
    {"id": 1, "name": "Team", "template_type": "team", "global_assignments": None},
]}


def handler(r: httpx2.Request):
    if r.url.path == "/openapi.json":
        raise httpx2.ConnectError("offline")
    if r.url.path == "/api/v1/channels/managed":
        assert r.url.params.get("include_deleted") == "false"
        return httpx2.Response(200, json=CHANNELS)
    if r.url.path == "/api/v1/groups":
        return httpx2.Response(200, json=GROUPS)
    if r.url.path == "/api/v1/templates":
        return httpx2.Response(200, json=TEMPLATES)
    return httpx2.Response(404, json={"detail": "nf"})


async def test_summary_joins_groups_and_templates(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(handler))
    async with Client(mcp) as c:
        res = (await c.call_tool("get_event_channels_summary", {})).data
    assert res["count"] == 2
    first, second = res["channels"]
    assert first["channel_number"] == 2001          # sorted by number
    assert first["group_name"] is None and first["template_name"] is None
    assert second["group_name"] == "MLB" and second["group_stream_count"] == 30
    assert second["template_id"] == 6 and second["template_name"] == "Baseball"
    assert second["tvg_id"] == "teamarr-event-1-x"
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement curated/channels.py**

```python
from __future__ import annotations

from fastmcp import FastMCP

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext


def _items(payload, key: str) -> list[dict]:
    return payload if isinstance(payload, list) else payload.get(key, [])


def resolve_template(templates: list[dict], league: str | None, sport: str | None) -> dict | None:
    events = [t for t in templates if t.get("template_type") == "event"]
    for t in events:
        for a in t.get("global_assignments") or []:
            if league and league in (a.get("leagues") or []):
                return t
    for t in events:
        for a in t.get("global_assignments") or []:
            if sport and sport in (a.get("sports") or []):
                return t
    return None


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    @mcp.tool(tags={"teamarr", "read"})
    async def get_event_channels_summary(include_deleted: bool = False) -> dict:
        """One-call overview of Teamarr's live and upcoming event channels: channel number,
        name, event, league, source group (with its stream count), the event template that
        applies, Dispatcharr channel id, tvg-id and sync status. Sorted by channel number."""
        channels = _items(
            await api.get("/api/v1/channels/managed",
                          params={"include_deleted": str(include_deleted).lower()}),
            "channels",
        )
        groups = {g["id"]: g for g in _items(await api.get("/api/v1/groups"), "groups")}
        templates = _items(await api.get("/api/v1/templates"), "templates")
        rows = []
        for ch in channels:
            g = groups.get(ch.get("event_epg_group_id"))
            t = resolve_template(templates, ch.get("league"), ch.get("sport"))
            rows.append({
                "channel_number": ch.get("channel_number"),
                "channel_name": ch.get("channel_name"),
                "event_name": ch.get("event_name"),
                "event_date": ch.get("event_date"),
                "sport": ch.get("sport"),
                "league": ch.get("league"),
                "sync_status": ch.get("sync_status"),
                "group_id": ch.get("event_epg_group_id"),
                "group_name": (g.get("display_name") or g.get("name")) if g else None,
                "group_stream_count": g.get("stream_count") if g else None,
                "template_id": t["id"] if t else None,
                "template_name": t["name"] if t else None,
                "dispatcharr_channel_id": ch.get("dispatcharr_channel_id"),
                "tvg_id": ch.get("tvg_id"),
            })
        rows.sort(key=lambda r: (r["channel_number"] is None, r["channel_number"] or 0))
        return {"count": len(rows), "channels": rows}

    ctx.curated_tool_names.append("get_event_channels_summary")
```

Add `channels` to the module tuple.

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Add get_event_channels_summary tool

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: `find_unmatched_streams`

**Files:**
- Create: `teamarr_mcp/curated/matching.py`, `tests/test_curated_matching.py`
- Modify: `teamarr_mcp/curated/__init__.py` (add `matching`)

**Interfaces:**
- Produces tool `find_unmatched_streams(group_id: int | None = None, reason: str | None = None, limit: int = 200) -> dict` → `{"run_id", "count", "by_reason": {reason: n}, "groups": [ {group_id, group_name, regex: {...enabled custom regexes...}, streams: [ {stream_id, stream_name, reason, detail, parsed_team1, parsed_team2, detected_league} ]} ]}`.

Teamarr facts: `GET /api/v1/epg/failed-matches?group_id=&reason=&limit=&run_id=` → `{"count", "run_id", "group_id", "reason_filter", "failures": [ {id, run_id, group_id, group_name, stream_id, stream_name, reason, exclusion_reason, detail, parsed_team1, parsed_team2, detected_league} ]}`. `GET /api/v1/groups` items carry `custom_regex_<x>` and `custom_regex_<x>_enabled` for x in `teams, time, date, day, month, league, event_name, fighters`, plus `stream_include_regex(_enabled)`, `stream_exclude_regex(_enabled)`, `stream_timezone`.

- [ ] **Step 1: Write the failing test**

`tests/test_curated_matching.py`:
```python
import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server

FAILS = {"count": 3, "run_id": 137, "group_id": None, "reason_filter": None, "failures": [
    {"id": 1, "run_id": 137, "group_id": 2, "group_name": "PPV", "stream_id": 11, "stream_name": "EVENT 01: X",
     "reason": "no_event_card_match", "detail": "No matching event card", "parsed_team1": None,
     "parsed_team2": None, "detected_league": None},
    {"id": 2, "run_id": 137, "group_id": 2, "group_name": "PPV", "stream_id": 12, "stream_name": "EVENT 02: Y",
     "reason": "unmatched", "detail": "", "parsed_team1": "A", "parsed_team2": "B", "detected_league": "ufc"},
    {"id": 3, "run_id": 137, "group_id": 3, "group_name": "Sky", "stream_id": 13, "stream_name": "S 01: Z",
     "reason": "unmatched", "detail": "", "parsed_team1": None, "parsed_team2": None, "detected_league": None},
]}
GROUPS = {"groups": [
    {"id": 2, "name": "PPV Events | 1", "display_name": "PPV", "custom_regex_teams": r"(.+) v (.+)",
     "custom_regex_teams_enabled": True, "custom_regex_time": None, "custom_regex_time_enabled": False,
     "stream_include_regex": "EVENT", "stream_include_regex_enabled": True, "stream_timezone": "US/Eastern"},
    {"id": 3, "name": "Sky", "display_name": None, "custom_regex_teams_enabled": False},
]}


def handler(r: httpx2.Request):
    if r.url.path == "/openapi.json":
        raise httpx2.ConnectError("offline")
    if r.url.path == "/api/v1/epg/failed-matches":
        assert r.url.params.get("limit") == "200"
        assert "group_id" not in r.url.params
        return httpx2.Response(200, json=FAILS)
    if r.url.path == "/api/v1/groups":
        return httpx2.Response(200, json=GROUPS)
    return httpx2.Response(404, json={"detail": "nf"})


async def test_groups_failures_with_regex_context(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(handler))
    async with Client(mcp) as c:
        res = (await c.call_tool("find_unmatched_streams", {})).data
    assert res["run_id"] == 137 and res["count"] == 3
    assert res["by_reason"] == {"no_event_card_match": 1, "unmatched": 2}
    ppv = next(g for g in res["groups"] if g["group_id"] == 2)
    assert ppv["group_name"] == "PPV"
    assert ppv["regex"] == {"teams": r"(.+) v (.+)", "stream_include": "EVENT",
                            "stream_timezone": "US/Eastern"}
    assert [s["stream_id"] for s in ppv["streams"]] == [11, 12]
    assert ppv["streams"][1]["parsed_team1"] == "A"
    sky = next(g for g in res["groups"] if g["group_id"] == 3)
    assert sky["regex"] == {}
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement curated/matching.py**

```python
from __future__ import annotations

from collections import Counter

from fastmcp import FastMCP

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext

_REGEX_FIELDS = ("teams", "time", "date", "day", "month", "league", "event_name", "fighters")


def active_regexes(group: dict) -> dict:
    out = {}
    for f in _REGEX_FIELDS:
        if group.get(f"custom_regex_{f}_enabled") and group.get(f"custom_regex_{f}"):
            out[f] = group[f"custom_regex_{f}"]
    for f in ("stream_include", "stream_exclude"):
        if group.get(f"{f}_regex_enabled") and group.get(f"{f}_regex"):
            out[f] = group[f"{f}_regex"]
    if group.get("stream_timezone"):
        out["stream_timezone"] = group["stream_timezone"]
    return out


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    @mcp.tool(tags={"teamarr", "read"})
    async def find_unmatched_streams(
        group_id: int | None = None, reason: str | None = None, limit: int = 200
    ) -> dict:
        """Streams in your source groups that produced no event channel in the latest EPG
        run, grouped by source group with that group's active custom regexes and timezone
        alongside, so you can tune parsing for provider naming formats such as
        `Team1 HH:MM Team2 DD/MM`. Reasons include `unmatched`, `no_event_card_match`,
        `excluded_league`. Filter with `group_id` and/or `reason`."""
        params: dict = {"limit": limit}
        if group_id is not None:
            params["group_id"] = group_id
        if reason:
            params["reason"] = reason
        failed = await api.get("/api/v1/epg/failed-matches", params=params)
        failures = failed.get("failures", []) if isinstance(failed, dict) else failed
        groups_payload = await api.get("/api/v1/groups")
        groups = {g["id"]: g for g in (groups_payload.get("groups", [])
                                       if isinstance(groups_payload, dict) else groups_payload)}
        by_group: dict[int, list[dict]] = {}
        for f in failures:
            by_group.setdefault(f.get("group_id"), []).append({
                "stream_id": f.get("stream_id"),
                "stream_name": f.get("stream_name"),
                "reason": f.get("reason"),
                "detail": f.get("detail"),
                "parsed_team1": f.get("parsed_team1"),
                "parsed_team2": f.get("parsed_team2"),
                "detected_league": f.get("detected_league"),
            })
        out_groups = []
        for gid, streams in by_group.items():
            g = groups.get(gid, {})
            out_groups.append({
                "group_id": gid,
                "group_name": g.get("display_name") or g.get("name")
                or next((f["group_name"] for f in failures if f.get("group_id") == gid), None),
                "regex": active_regexes(g),
                "streams": streams,
            })
        return {
            "run_id": failed.get("run_id") if isinstance(failed, dict) else None,
            "count": len(failures),
            "by_reason": dict(sorted(Counter(f.get("reason") for f in failures).items())),
            "groups": out_groups,
        }

    ctx.curated_tool_names.append("find_unmatched_streams")
```

Add `matching` to the module tuple.

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Add find_unmatched_streams tool

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: `check_tsdb_gated_subscriptions`

**Files:**
- Create: `teamarr_mcp/curated/subscriptions.py`, `tests/test_curated_subscriptions.py`
- Modify: `teamarr_mcp/curated/__init__.py` (add `subscriptions`)

**Interfaces:**
- Produces tool `check_tsdb_gated_subscriptions() -> dict` → `{"tsdb_key_configured": bool, "gated_leagues": [ {slug, name, sport} ], "custom_leagues_count": int, "message": str}`.

Teamarr facts (v2.17.0, issue #676): TheSportsDB is premium-key only; leagues with `provider == "tsdb"` in `GET /api/v1/cache/leagues` (`{"count", "leagues": [ {slug, provider, name, sport, ...} ]}`) and all custom leagues (`GET /api/v1/leagues/custom` → list or `{"leagues": [...]}`) return no fixtures unless `tsdb_api_key` is set. The key lives in `GET /api/v1/settings/display` as `tsdb_api_key` (masked when set, `null` when unset). Subscribed leagues: `GET /api/v1/sports-subscription` → `{"leagues": [slugs]}`.

- [ ] **Step 1: Write the failing test**

`tests/test_curated_subscriptions.py`:
```python
import httpx2
from fastmcp import Client

from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server


def make_handler(key):
    def handler(r: httpx2.Request):
        if r.url.path == "/openapi.json":
            raise httpx2.ConnectError("offline")
        if r.url.path == "/api/v1/settings/display":
            return httpx2.Response(200, json={"tsdb_api_key": key})
        if r.url.path == "/api/v1/sports-subscription":
            return httpx2.Response(200, json={"leagues": ["nfl", "ipl", "sa20"]})
        if r.url.path == "/api/v1/cache/leagues":
            return httpx2.Response(200, json={"count": 3, "leagues": [
                {"slug": "nfl", "provider": "espn", "name": "NFL", "sport": "football"},
                {"slug": "ipl", "provider": "tsdb", "name": "IPL", "sport": "cricket"},
                {"slug": "sa20", "provider": "tsdb", "name": "SA20", "sport": "cricket"},
                {"slug": "bbl", "provider": "tsdb", "name": "BBL", "sport": "cricket"},
            ]})
        if r.url.path == "/api/v1/leagues/custom":
            return httpx2.Response(200, json=[{"slug": "my-league"}])
        return httpx2.Response(404, json={"detail": "nf"})
    return handler


async def test_gated_when_no_key(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(make_handler(None)))
    async with Client(mcp) as c:
        res = (await c.call_tool("check_tsdb_gated_subscriptions", {})).data
    assert res["tsdb_key_configured"] is False
    assert [g["slug"] for g in res["gated_leagues"]] == ["ipl", "sa20"]
    assert res["custom_leagues_count"] == 1
    assert "premium" in res["message"].lower()


async def test_nothing_gated_with_key(make_client):
    mcp = await build_server(Settings(url="http://t"), client=make_client(make_handler("********")))
    async with Client(mcp) as c:
        res = (await c.call_tool("check_tsdb_gated_subscriptions", {})).data
    assert res["tsdb_key_configured"] is True
    assert res["gated_leagues"] == []
```

- [ ] **Step 2: Run to verify failure** → FAIL.

- [ ] **Step 3: Implement curated/subscriptions.py**

```python
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext


def register(mcp: FastMCP, api: TeamarrApi, ctx: ServerContext) -> None:
    @mcp.tool(tags={"teamarr", "read"})
    async def check_tsdb_gated_subscriptions() -> dict:
        """Find subscribed leagues that will produce NO fixtures because they come from
        TheSportsDB, which Teamarr only supports with a premium API key. Also counts custom
        leagues (always TSDB-backed). Use this when a subscribed league shows no events.
        The key is set via `update_settings(block="display", changes={"tsdb_api_key": ...})`."""
        display = await api.get("/api/v1/settings/display")
        has_key = bool(display.get("tsdb_api_key"))
        subscribed = set((await api.get("/api/v1/sports-subscription")).get("leagues") or [])
        cache = await api.get("/api/v1/cache/leagues")
        leagues = cache.get("leagues", []) if isinstance(cache, dict) else cache
        try:
            custom = await api.get("/api/v1/leagues/custom")
            custom_count = len(custom.get("leagues", []) if isinstance(custom, dict) else custom)
        except ToolError:
            custom_count = 0
        gated = [] if has_key else [
            {"slug": lg["slug"], "name": lg.get("name"), "sport": lg.get("sport")}
            for lg in leagues if lg.get("provider") == "tsdb" and lg.get("slug") in subscribed
        ]
        gated.sort(key=lambda x: x["slug"])
        if has_key:
            message = "A TheSportsDB premium key is configured; no subscriptions are gated."
        elif gated or custom_count:
            message = (f"{len(gated)} subscribed league(s) and {custom_count} custom league(s) "
                       "need a TheSportsDB premium key and currently return no fixtures.")
        else:
            message = "No TheSportsDB-backed subscriptions; no premium key needed."
        return {"tsdb_key_configured": has_key, "gated_leagues": gated,
                "custom_leagues_count": custom_count, "message": message}

    ctx.curated_tool_names.append("check_tsdb_gated_subscriptions")
```

Add `subscriptions` to the module tuple so it reads `(info, settings, templates, channels, matching, subscriptions)`.

- [ ] **Step 4: Run whole suite** → `uv run pytest -v` all PASS.

- [ ] **Step 5: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Add check_tsdb_gated_subscriptions tool

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: `main()` entry point and transports

**Files:**
- Modify: `teamarr_mcp/server.py` (append `main`)
- Create: `tests/test_main.py`

**Interfaces:**
- Produces `def main(argv: list[str] | None = None) -> None` reading `Settings.from_env()`, configuring logging, building the server, and calling `mcp.run(transport="stdio", show_banner=False)` or `mcp.run(transport="http", host=..., port=..., path="/mcp", show_banner=False)`. `--version` prints version and exits 0.

- [ ] **Step 1: Write the failing test**

`tests/test_main.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure** → `uv run pytest tests/test_main.py -v` FAIL (`main` missing).

- [ ] **Step 3: Append main() to server.py**

```python
def main(argv: list[str] | None = None) -> None:
    import argparse
    import asyncio
    import sys

    parser = argparse.ArgumentParser(prog="teamarr-mcp", description="MCP server for Teamarr")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        print(f"teamarr-mcp {__version__}")
        raise SystemExit(0)

    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    mcp = asyncio.run(build_server(settings))
    if settings.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(transport="http", host=settings.host, port=settings.port, path="/mcp",
                show_banner=False)
```

Logging must go to stderr: in stdio mode stdout is the MCP channel.

- [ ] **Step 4: Run tests and a real smoke**

Run: `uv run pytest tests/test_main.py -v` → PASS.
Smoke (no Teamarr needed, vendored fallback):
```bash
uv run teamarr-mcp --version
TEAMARR_URL=http://127.0.0.1:1 TEAMARR_MCP_TRANSPORT=http TEAMARR_MCP_PORT=8765 timeout 8 uv run teamarr-mcp || true
```
Expected: version line; then a warning about the unreachable spec and uvicorn listening on 8765 until the timeout kills it. If `asyncio.run` inside `main` conflicts with `mcp.run` creating its own loop, this is fine because `build_server`'s loop is closed before `mcp.run` starts.

- [ ] **Step 5: Ruff and commit**

```bash
uv run ruff check . && git add -A && git commit -m "Add CLI entry point with stdio and http transports

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: Opt-in live tests against the real instance

**Files:**
- Create: `tests/live/__init__.py`, `tests/live/test_live_readonly.py`

**Interfaces:**
- Consumes everything. Skipped unless `TEAMARR_TEST_URL` is set.

- [ ] **Step 1: Write the live tests**

`tests/live/test_live_readonly.py`:
```python
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
```

- [ ] **Step 2: Run against the live instance (read-only)**

Run: `TEAMARR_TEST_URL=http://192.168.1.63:9195 uv run pytest tests/live -v`
Expected: 6 passed. Fix any shape mismatch in the curated tool (not in the test) and re-run the unit suite too.

- [ ] **Step 3: Live write round-trip (ASK THE USER FIRST)**

Only after the user says yes:
```bash
TEAMARR_TEST_URL=http://192.168.1.63:9195 uv run python - <<'EOF'
import asyncio, os
from fastmcp import Client
from teamarr_mcp.config import Settings
from teamarr_mcp.server import build_server
async def main():
    mcp = await build_server(Settings(url=os.environ["TEAMARR_TEST_URL"]))
    async with Client(mcp) as c:
        before = (await c.call_tool("get_lifecycle_settings", {})).data
        post = before.channel_post_buffer_minutes if hasattr(before, "channel_post_buffer_minutes") else before["channel_post_buffer_minutes"]
        await c.call_tool("update_settings", {"block": "lifecycle", "changes": {"channel_post_buffer_minutes": post}})
        after = (await c.call_tool("get_lifecycle_settings", {})).data
        print("BEFORE", before); print("AFTER ", after)
        assert str(before) == str(after), "fields changed!"
        print("round-trip OK: no fields lost")
asyncio.run(main())
EOF
```
Expected: `round-trip OK`. If the user declines, record in the README that the round trip was verified only against the mock.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "Add opt-in live read-only tests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 14: Docker packaging and spec refresh script

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `docker-compose.example.yml`, `scripts/refresh_spec.py`

- [ ] **Step 1: Dockerfile**

```dockerfile
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY teamarr_mcp ./teamarr_mcp
RUN uv pip install --system --no-cache . \
    && useradd --create-home --uid 1000 mcp
USER mcp
ENV TEAMARR_URL=http://localhost:9195 \
    TEAMARR_MCP_TRANSPORT=http \
    TEAMARR_MCP_HOST=0.0.0.0 \
    TEAMARR_MCP_PORT=8000 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/mcp', timeout=3).status < 500 else 1)" || exit 1
ENTRYPOINT ["teamarr-mcp"]
```
Note: an MCP `GET /mcp` without a session may return 4xx; the healthcheck treats anything below 500 as alive. If CI shows the container unhealthy, replace the check with `CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 8000), 3)"]`.

`.dockerignore`:
```
.git
.venv
tests
docs
.github
__pycache__
*.pyc
.pytest_cache
.ruff_cache
```

- [ ] **Step 2: docker-compose.example.yml**

```yaml
services:
  teamarr-mcp:
    image: ghcr.io/lukeeexd/teamarr-mcp:latest
    container_name: teamarr-mcp
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      TEAMARR_URL: http://teamarr:9195        # or http://192.168.1.x:9195
      # TEAMARR_API_KEY: ""                    # only if your Teamarr gains auth
      TEAMARR_MCP_ENABLE_DESTRUCTIVE: "false"  # deletes, restores, cache clears
      TEAMARR_MCP_READ_ONLY: "false"           # expose GET tools only
```

- [ ] **Step 3: scripts/refresh_spec.py**

```python
"""Refresh teamarr_mcp/specs/openapi.json from a running Teamarr.

Usage: uv run python scripts/refresh_spec.py http://192.168.1.63:9195
"""

import json
import sys
from pathlib import Path

import httpx2

url = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9195").rstrip("/")
spec = httpx2.get(f"{url}/openapi.json", timeout=30).raise_for_status().json()
out = Path(__file__).resolve().parent.parent / "teamarr_mcp" / "specs" / "openapi.json"
out.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
ops = sum(1 for p in spec["paths"].values() for m in p if m in ("get", "post", "put", "patch", "delete"))
print(f"wrote {out} (Teamarr {spec['info'].get('version')}, {len(spec['paths'])} paths, {ops} ops)")
```

- [ ] **Step 4: Verify what can be verified locally**

Docker is not installed on this machine. Verify the wheel builds and installs the way the Dockerfile does:
```bash
uv build && uv venv .tmpvenv --python 3.12 && uv pip install --python .tmpvenv/Scripts/python.exe dist/*.whl && .tmpvenv/Scripts/teamarr-mcp --version && rm -rf .tmpvenv dist
```
Expected: version prints from the installed wheel (proves `specs/openapi.json` ships in the wheel; if `--version` works but a later `import` of the vendored spec fails, add the hatch `include` from Task 2 Step 5). Then run `uv run python scripts/refresh_spec.py http://192.168.1.63:9195` and confirm `git diff --stat teamarr_mcp/specs/openapi.json` shows no change (live equals vendored).

- [ ] **Step 5: Commit**

```bash
uv run ruff check . && git add -A && git commit -m "Add Dockerfile, compose example and spec refresh script

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 15: README and CI workflows

**Files:**
- Create: `README.md`, `.github/workflows/ci.yml`, `.github/workflows/publish.yml`

- [ ] **Step 1: README.md**

Write these sections, in order, with this content:

1. **Title + one-liner**: `# teamarr-mcp` — "An MCP server for [Teamarr](https://github.com/Pharaoh-Labs/teamarr). Lets Claude Desktop, Claude Code or any MCP client read and change your sports-EPG configuration: teams, event groups, templates, settings, channels, Dispatcharr sync."
2. **How it works**: two tiers. Generated tier from Teamarr's own `/openapi.json` at startup (falls back to a vendored spec for Teamarr 2.17.0), so new endpoints appear without a release of this server. Curated tier: table of the six curated tools with one-line descriptions (from the docstrings in Tasks 6–11), and a paragraph "Why `update_settings`": Teamarr's settings PUTs replace the whole block.
3. **Quick start: Docker (HTTP)**: `docker run -d -p 8000:8000 -e TEAMARR_URL=http://192.168.1.x:9195 ghcr.io/lukeeexd/teamarr-mcp:latest`, then client snippets. Claude Code: `claude mcp add --transport http teamarr http://localhost:8000/mcp`. Claude Desktop / `.mcp.json`:
   ```json
   { "mcpServers": { "teamarr": { "type": "http", "url": "http://localhost:8000/mcp" } } }
   ```
   Link to `docker-compose.example.yml`.
4. **Quick start: local (stdio)**: `uv tool install teamarr-mcp` or `pipx install teamarr-mcp`; Claude Code: `claude mcp add teamarr -e TEAMARR_URL=http://192.168.1.x:9195 -e TEAMARR_MCP_TRANSPORT=stdio -- teamarr-mcp`; Claude Desktop JSON:
   ```json
   { "mcpServers": { "teamarr": { "command": "teamarr-mcp",
       "env": { "TEAMARR_URL": "http://192.168.1.x:9195", "TEAMARR_MCP_TRANSPORT": "stdio" } } } }
   ```
5. **Configuration**: the env table from the spec, verbatim, plus a **Safety** paragraph: default hides deletes/restores/cache clears; `TEAMARR_MCP_READ_ONLY=true` for a browse-only server; always-hidden routes (support bundle, backup download, XMLTV, SSE log stream, raw settings PUTs).
6. **Tools**: how names are derived (`list_teams`, `get_team`, `patch_team`…), count per mode (fill from `test_counts` numbers), `teamarr_info` to inspect.
7. **Teamarr ecosystem notes**: Dispatcharr consumers should append `?tvg_id_source=tvg_id` to Dispatcharr M3U/EPG URLs so ids stay stable (`teamarr-event-<id>-<session>`) despite renumbering; Podium `stream_stats` feed stream ordering and Teamarr rewrites stream order every run; optional matchup art via `epg.art_base_url` (game-thumbs); TheSportsDB is premium-key-only, use `check_tsdb_gated_subscriptions`; known upstream cosmetic bug: postgame title "<session> Complete" while description says "has not yet ended" when the provider returns no final status.
8. **Development**: `uv sync --extra dev`, `uv run pytest`, `uv run ruff check .`, live tests via `TEAMARR_TEST_URL`, `scripts/refresh_spec.py`.
9. **Licence**: MIT.

- [ ] **Step 2: ci.yml**

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: ${{ matrix.python }}
      - run: uv sync --extra dev
      - run: uv run ruff check .
      - run: uv run pytest -q
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: false
          tags: teamarr-mcp:ci
```

- [ ] **Step 3: publish.yml**

```yaml
name: Publish
on:
  push:
    tags: ["v*"]
permissions:
  contents: read
  packages: write
  id-token: write
jobs:
  ghcr:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/metadata-action@v5
        id: meta
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest
      - uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
  pypi:
    runs-on: ubuntu-latest
    environment: pypi
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@release/v1
```
README must note: PyPI publishing uses trusted publishing; the repo owner must add the GitHub publisher on pypi.org for project `teamarr-mcp` (environment `pypi`) before tagging.

- [ ] **Step 4: Validate and commit**

```bash
uv run python -c "import yaml" 2>/dev/null || uv pip install --python .venv/Scripts/python.exe pyyaml
uv run python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('yaml ok')"
uv run ruff check . && uv run pytest -q
git add -A && git commit -m "Add README and CI/publish workflows

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 16: Create the public GitHub repo and push

**Files:** none new.

- [ ] **Step 1: Final gate**

Run: `uv run ruff check . && uv run pytest -q` → all green. `git status` clean.

- [ ] **Step 2: Create the repo**

Use the GitHub MCP tool `create_repository` with `name="teamarr-mcp"`, `description="MCP server for Teamarr — manage your sports EPG from Claude or any MCP client"`, `private=false`, `autoInit=false`. Then:
```bash
git remote add origin https://github.com/lukeeexd/teamarr-mcp.git
git push -u origin main
```
If the push prompts for credentials non-interactively and fails, tell the user to run `! git push -u origin main` themselves.

- [ ] **Step 3: Confirm CI**

Check the Actions run via the GitHub MCP tools (`list_commits` shows the pushed SHA; the CI status is on the commit). Report the result. Do not tag `v0.1.0` until the user confirms the PyPI trusted publisher is configured.

- [ ] **Step 4: Draft the upstream note**

Write `docs/upstream-issue-draft.md` containing a short issue for `Pharaoh-Labs/teamarr`: title "Community MCP server: teamarr-mcp", body linking the repo, stating it is generated from `/openapi.json` plus curated tools, and asking two things: (1) keep `operationId`s stable or add explicit ones, (2) consider making settings PUTs partial (PATCH semantics) since whole-block replace drops fields. Commit it. The user posts it.

```bash
git add -A && git commit -m "Add upstream issue draft

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push
```
