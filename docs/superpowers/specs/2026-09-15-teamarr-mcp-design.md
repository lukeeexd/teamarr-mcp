# teamarr-mcp design

Date: 2026-09-15. Target: Teamarr v2.17.0 (API drifts weekly; design for that).

## Goal

An open-source MCP server that lets any MCP client (Claude Desktop, Claude Code,
others) read and change a Teamarr instance's configuration. Public repo
`lukeeexd/teamarr-mcp`, MIT, all configuration via environment variables,
nothing hard-coded to one deployment. Modelled on dispatcharr-mcp for packaging
and UX, but built on FastMCP 4's OpenAPI provider instead of hand-written tools.

## Facts established against v2.17.0

- `/openapi.json` is enabled. 164 paths, 225 operations
  (113 GET, 55 POST, 34 PUT, 20 DELETE, 3 PATCH), 193 schemas, every operation
  has an `operationId`, none deprecated. The spec served by a live instance is
  identical to the one produced from source.
- `operationId`s are FastAPI auto-names: `<function>_<path slug>_<method>`,
  e.g. `list_teams_api_v1_teams_get`. Stripping the suffix produces collisions
  (`update_team` for PUT and PATCH; `create_keyword` in two routers;
  `update` / `delete` for numbering exceptions).
- No authentication on the API today.
- `/health` returns `{"status","version","startup","runtime"}`.
- `PUT /api/v1/settings/lifecycle` takes the full `LifecycleSettingsModel`.
  Omitted fields take model defaults, so a partial PUT resets them
  (e.g. `channel_range_start`).
- `PUT /api/v1/settings/dispatcharr` forwards every field, `None` included,
  to the DB update. `GET` returns `password` masked as `********`; the server
  treats that sentinel as "keep" (`unmask_or_skip`).
- Enum validation is manual in route handlers and returns HTTP 400 with
  `detail` like `Invalid channel_stability_mode. Valid: [...]`. Schemas do not
  carry these enums, so the client cannot pre-validate; it must surface the
  message.

## Architecture

Two tiers assembled into one FastMCP server.

### Generated tier

`FastMCP.from_openapi(spec, client, route_maps=..., mcp_component_fn=...)`.

- **Spec source.** At startup fetch `{TEAMARR_URL}/openapi.json`. On failure,
  or when `TEAMARR_OPENAPI_PATH` is set, load a vendored copy at
  `teamarr_mcp/specs/openapi.json`. Record which source was used; expose it via
  `teamarr_info`. `scripts/refresh_spec.py` refreshes the vendored copy from a
  URL or from a Teamarr source checkout.
- **Naming.** For each route compute FastAPI's suffix from its path and method
  (`path.replace("/","_")` with braces removed, plus `_<method>`), strip it from
  the `operationId`, and use the remainder as the tool name. Apply an explicit
  override table for known collisions, then a fallback that appends the HTTP
  method to any remaining duplicate. Result must be unique, snake_case,
  ≤ 64 chars. A test runs this over the whole vendored spec.

  Known overrides:

  | Route | Name |
  |---|---|
  | `PATCH /api/v1/teams/{team_id}` | `patch_team` |
  | `POST /api/v1/detection-keywords` | `create_detection_keyword` |
  | `PUT /api/v1/detection-keywords/id/{keyword_id}` | `update_detection_keyword` |
  | `DELETE /api/v1/detection-keywords/id/{keyword_id}` | `delete_detection_keyword` |
  | `PUT /api/v1/numbering-exceptions/{exception_id}` | `update_numbering_exception` |
  | `DELETE /api/v1/numbering-exceptions/{exception_id}` | `delete_numbering_exception` |

  The implementation may add rows as the collision test reveals them.
- **Component type.** Every included route becomes a tool. No MCP resources or
  resource templates.
- **Route maps**, in order (first match wins):
  1. Always exclude: support bundle, backup download, XMLTV output
     (`/api/v1/epg/xmltv`), log tail/stream endpoints, and every
     `PUT /api/v1/settings/*` (replaced by the curated `update_settings`).
     `PUT /api/v1/settings/stream-ordering/scopes/{id}` stays: it is a
     per-item update, not a block.
  2. If `TEAMARR_MCP_READ_ONLY`: exclude all non-GET.
  3. Destructive set, excluded unless `TEAMARR_MCP_ENABLE_DESTRUCTIVE`:
     every DELETE; `POST /api/v1/backup` and `/backup/{f}/restore`;
     `POST /api/v1/templates/restore-defaults`; `POST /api/v1/channels/reset`;
     `POST /api/v1/groups/cache/clear`, `.../clear-all`,
     `.../{group_id}/cache/clear`; `POST /api/v1/game-data-cache/clear`.
  4. Everything else: tool.
- **Descriptions.** OpenAPI summary/description, prefixed `[destructive]` for
  routes in the destructive set.

### Curated tier

Hand-written tools in `teamarr_mcp/curated/`, one module each, sharing the
same httpx client.

| Tool | Behaviour |
|---|---|
| `teamarr_info()` | `/health` result, Teamarr version, spec source (live/vendored + version), tool count, active flags. |
| `update_settings(block, changes, replace=False)` | `GET /api/v1/settings/{block}`, shallow-merge `changes` over it, `PUT`. Drops any field whose current value is the mask `********` unless `changes` sets it. `replace=True` PUTs `changes` verbatim. Returns the PUT response. `block` is validated against the settings paths present in the loaded spec. |
| `set_template_filler(field, text, template_ids=None)` | For each event template (all, or the given ids) GET, set `field` (pregame/postgame filler fields as named in the template schema), PUT if changed. Returns changed/unchanged/failed ids. Description documents `{relative_day_title}` / `{relative_day}` vs `{game_day}`. |
| `get_event_channels_summary()` | `/api/v1/channels/managed` joined with `/api/v1/groups` and `/api/v1/templates`: number, name, event, league, group display name, template name, group stream count, sync status. |
| `find_unmatched_streams(group_id=None)` | For enabled event groups, list source streams that produced no event channel, with the group's current regex settings, to drive regex tuning. Uses the group stream/match endpoints available in the spec. |
| `list_premium_gated_subscriptions()` | Subscribed leagues flagged premium when no TheSportsDB premium key is configured, so users learn why fixtures are empty. |

`find_unmatched_streams` and `list_premium_gated_subscriptions` depend on
endpoint shapes to be confirmed during implementation against the live
instance; if an endpoint needed does not exist, the tool is dropped and the
README says so.

## Configuration

| Var | Default | Notes |
|---|---|---|
| `TEAMARR_URL` | `http://localhost:9195` | |
| `TEAMARR_API_KEY` | unset | Sent only if set. |
| `TEAMARR_API_KEY_HEADER` | `X-API-Key` | Header name for the key; Teamarr has no auth yet, so this is a pluggable guess. |
| `TEAMARR_MCP_TRANSPORT` | `http` | `http` or `stdio`. |
| `TEAMARR_MCP_HOST` | `0.0.0.0` | HTTP only. |
| `TEAMARR_MCP_PORT` | `8000` | HTTP only. |
| `TEAMARR_MCP_ENABLE_DESTRUCTIVE` | `false` | |
| `TEAMARR_MCP_READ_ONLY` | `false` | |
| `TEAMARR_OPENAPI_PATH` | unset | Force a local spec file. |
| `TEAMARR_MCP_LOG_LEVEL` | `INFO` | |

Booleans accept `1/true/yes/on` case-insensitively.

## Error handling

- HTTP 4xx/5xx from Teamarr → tool error whose message is
  `HTTP <status> <METHOD> <path>: <detail>` with `detail` verbatim (string or
  JSON). This carries the enum lists to the model.
- Connection errors → tool error naming the configured URL.
- Startup: if the live spec is unreachable, log a warning and use the vendored
  spec. If neither is available, exit non-zero with a clear message.

## Packaging and delivery

- `uv` project, hatchling build, `requires-python >=3.11`,
  deps `fastmcp>=4,<5`, `httpx>=0.27`. Dev deps: `pytest`, `pytest-asyncio`,
  `respx`, `ruff`.
- Console script `teamarr-mcp` → `teamarr_mcp.server:main`.
- Dockerfile: `python:3.12-slim`, `uv` install, non-root user, `EXPOSE 8000`,
  default HTTP transport. `docker-compose.example.yml`.
- README: what it is, ecosystem notes (Dispatcharr `?tvg_id_source=tvg_id`,
  Podium stream_stats overwritten each run, game-thumbs art, TheSportsDB
  premium gating, known postgame-title cosmetic bug), config table, tool
  overview, Claude Desktop / Claude Code / `.mcp.json` snippets for HTTP and
  stdio, Docker and local install, safety flags.
- MIT licence.
- GitHub Actions: `ci.yml` (ruff check + pytest on push/PR),
  `publish.yml` (on `v*` tag: GHCR multi-arch image, PyPI via trusted
  publishing). Docker is not installed on the dev machine; CI validates the
  image.
- Repo `lukeeexd/teamarr-mcp`, public, created via the GitHub connection once
  tests pass. Commits carry no co-author lines unless the harness rule applies.

## Testing

- Unit (`respx`): naming uniqueness over the vendored spec; route gating under
  each flag combination (counts and specific tools present/absent); merge
  semantics of `update_settings` including masked password and `replace=True`;
  error mapping preserves `detail`; spec fallback path.
- Live, opt-in via `TEAMARR_TEST_URL` (read-only): health, tool count matches
  spec operation count minus exclusions, `get_event_channels_summary` returns
  rows, `teamarr_info` reports `live` spec.
- Live write, run once manually with user confirmation: `update_settings`
  on `lifecycle` with an unchanged value; assert the GET afterwards equals the
  GET before.

## Out of scope

- Upstream issue/PR on Teamarr (drafted, posted by the user).
- MCP resources, prompts, OAuth, multi-instance support.
