# teamarr-mcp

An [MCP](https://modelcontextprotocol.io) server for [Teamarr](https://github.com/Pharaoh-Labs/teamarr).
Lets Claude Desktop, Claude Code or any MCP client read and change your sports-EPG
configuration: teams, event groups, templates, settings, channels and Dispatcharr sync.

## How it works

**Generated tier.** At startup the server fetches your Teamarr's own `/openapi.json` and turns
every endpoint into an MCP tool with a clean name (`list_teams`, `get_team`, `patch_team`,
`sync_lifecycle`, ...). New Teamarr endpoints appear without a new release of this server. If
Teamarr is unreachable at startup, a vendored copy of the Teamarr 2.17.0 spec is used instead.

**Curated tier.** Hand-written tools that encode Teamarr API behaviour you would otherwise
learn the hard way:

| Tool | What it does |
|---|---|
| `teamarr_info` | Instance URL, version, health, which spec was loaded, tool counts, active safety flags. Call it first if a tool seems missing. |
| `update_settings(block, changes, replace=False)` | Read-merge-write for any `/api/v1/settings/<block>`. See below. |
| `set_template_filler(section, field, text, template_ids=None)` | Set one pregame/postgame filler field across all event templates in one call. |
| `get_event_channels_summary()` | Live and upcoming event channels with number, event, league, source group and stream count, applied template, Dispatcharr id, tvg-id, sync status. |
| `find_unmatched_streams(group_id=None, reason=None, limit=200)` | Streams from the last EPG run that produced no channel, grouped by source group with that group's active regexes and timezone, for regex tuning. |
| `check_tsdb_gated_subscriptions()` | Subscribed leagues that return no fixtures because they need a TheSportsDB premium key. |

**Why `update_settings` exists.** Teamarr's `PUT /api/v1/settings/<block>` replaces the whole
block. Omit `channel_range_start` from a lifecycle PUT and it silently resets; omit `epg_id` or
`default_channel_group_id` from a Dispatcharr PUT and they are gone. `update_settings` GETs the
block, merges your changes over it, drops masked secrets so the server keeps them, and PUTs the
result. The raw settings PUT tools are therefore hidden. Pass `replace=True` if you really want
whole-block semantics. Teamarr's enum validation errors (e.g. `Invalid channel_stability_mode.
Valid: ['compact', 'gap', 'strict']`) are passed through verbatim.

## Quick start: Docker (HTTP transport)

```bash
docker run -d --name teamarr-mcp -p 8000:8000 \
  -e TEAMARR_URL=http://192.168.1.x:9195 \
  ghcr.io/lukeeexd/teamarr-mcp:latest
```

Or use [`docker-compose.example.yml`](docker-compose.example.yml).

Connect a client to `http://<host>:8000/mcp`:

```bash
# Claude Code
claude mcp add --transport http teamarr http://localhost:8000/mcp
```

```json
// Claude Desktop config or a project .mcp.json
{
  "mcpServers": {
    "teamarr": { "type": "http", "url": "http://localhost:8000/mcp" }
  }
}
```

## Quick start: local install (stdio transport)

```bash
uv tool install teamarr-mcp      # or: pipx install teamarr-mcp
```

```bash
# Claude Code
claude mcp add teamarr \
  -e TEAMARR_URL=http://192.168.1.x:9195 \
  -e TEAMARR_MCP_TRANSPORT=stdio \
  -- teamarr-mcp
```

```json
// Claude Desktop config
{
  "mcpServers": {
    "teamarr": {
      "command": "teamarr-mcp",
      "env": {
        "TEAMARR_URL": "http://192.168.1.x:9195",
        "TEAMARR_MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

Claude Desktop config lives at `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS), `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/.config/Claude/claude_desktop_config.json` (Linux).

## Configuration

Everything is set through environment variables. Nothing is stored in client config except the
URL of this server.

| Variable | Default | Notes |
|---|---|---|
| `TEAMARR_URL` | `http://localhost:9195` | Base URL of your Teamarr. |
| `TEAMARR_API_KEY` | unset | Sent only if set. Teamarr has no API auth today; this is future-proofing. |
| `TEAMARR_API_KEY_HEADER` | `X-API-Key` | Header name used for the key. |
| `TEAMARR_MCP_TRANSPORT` | `http` | `http` or `stdio`. |
| `TEAMARR_MCP_HOST` | `0.0.0.0` | HTTP transport bind address. |
| `TEAMARR_MCP_PORT` | `8000` | HTTP transport port. The MCP endpoint is `/mcp`. |
| `TEAMARR_MCP_ENABLE_DESTRUCTIVE` | `false` | Expose deletes, backup restores, channel reset, cache clears. |
| `TEAMARR_MCP_READ_ONLY` | `false` | Expose GET tools only. |
| `TEAMARR_OPENAPI_PATH` | unset | Load the spec from this file instead of the live instance. |
| `TEAMARR_MCP_LOG_LEVEL` | `INFO` | Logs go to stderr. |

Booleans accept `1`, `true`, `yes`, `on` (case-insensitive).

### Safety

By default the server hides anything that deletes or resets data: every `DELETE`, both backup
restore endpoints, `templates/restore-defaults`, `channels/reset`, the match-cache and
game-data-cache clears, and clearing run history. Set `TEAMARR_MCP_ENABLE_DESTRUCTIVE=true` to
expose them; their descriptions are prefixed `[destructive]`.

`TEAMARR_MCP_READ_ONLY=true` gives you a browse-only server with GET tools only.

Some routes are never exposed: the support bundle and backup downloads (binary), the XMLTV
outputs (large documents), the SSE generation log stream, and the raw whole-block settings PUTs
(use `update_settings`).

## Tools

Tool names come from Teamarr's FastAPI route names with the auto-generated path suffix removed,
so `list_teams_api_v1_teams_get` becomes `list_teams`. Collisions are resolved explicitly
(`patch_team` vs `update_team`, `create_detection_keyword` vs `create_keyword`).

Against Teamarr 2.17.0 (225 API operations):

| Mode | Tools |
|---|---|
| default | 180 (174 generated + 6 curated) |
| `TEAMARR_MCP_READ_ONLY=true` | 110 |
| `TEAMARR_MCP_ENABLE_DESTRUCTIVE=true` | 208 |

Run `teamarr_info` to see the live numbers for your instance.

## Teamarr ecosystem notes

- **Dispatcharr.** Teamarr renumbers event channels constantly (`channel_stability_mode`, daily
  reset). Point Dispatcharr consumers at M3U/EPG URLs with `?tvg_id_source=tvg_id` so they key on
  the stable `teamarr-event-<id>` ids instead of channel numbers.
- **Podium.** Stream-ordering rules can consume `stream_stats` published by
  [Podium](https://github.com/lpukatch/podium). Teamarr rewrites the stream order every run, so
  do not hand-order streams in Dispatcharr.
- **Matchup art.** Optional artwork via `epg.art_base_url` pointing at a game-thumbs instance.
- **TheSportsDB.** Since Teamarr 2.16 TheSportsDB works only with a premium key. Leagues with
  `provider: tsdb` and all custom leagues return no fixtures without one. Use
  `check_tsdb_gated_subscriptions`, then `update_settings(block="display",
  changes={"tsdb_api_key": "..."})`.
- **Known upstream cosmetic bug.** A postgame title can read "<session> Complete" while the
  description says the event "has not yet ended" when the provider returns no final status.

## Development

```bash
uv sync --extra dev
uv run pytest                 # unit tests, mocked Teamarr
uv run ruff check .
TEAMARR_TEST_URL=http://192.168.1.x:9195 uv run pytest tests/live   # read-only live checks
uv run python scripts/refresh_spec.py http://192.168.1.x:9195       # refresh the vendored spec
```

The `update_settings` round trip was verified against a live Teamarr 2.17.0: a merged PUT of the
lifecycle block left every field, including `channel_range_start`, unchanged.

Releases are tagged `v*`. CI publishes a multi-arch image to GHCR and the package to PyPI via
trusted publishing, which requires the GitHub publisher to be registered on pypi.org for the
`teamarr-mcp` project (environment `pypi`) before the first tag.

## Licence

MIT
