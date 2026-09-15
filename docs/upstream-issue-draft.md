# Draft issue for Pharaoh-Labs/teamarr

**Title:** Community MCP server: teamarr-mcp

**Body:**

Hi — I've built an MCP server for Teamarr so Claude Desktop / Claude Code / any MCP client can
read and change a Teamarr instance's config: https://github.com/lukeeexd/teamarr-mcp

How it works:

- Generated tier: `FastMCP.from_openapi()` over the instance's own `/openapi.json` at startup
  (falls back to a vendored 2.17.0 spec). New endpoints show up automatically.
- Curated tier: a few hand-written tools for things the raw API makes easy to get wrong,
  chiefly `update_settings`, a read-merge-write wrapper for `PUT /api/v1/settings/<block>`
  (a partial lifecycle PUT resets `channel_range_start`; a partial Dispatcharr PUT drops
  `epg_id` / `default_channel_group_id`).
- Deletes / restores / cache clears are hidden unless explicitly enabled.

Two small asks that would make the generated tier more robust across releases:

1. **Stable `operationId`s.** Today they are FastAPI auto-names
   (`list_teams_api_v1_teams_get`). I strip the suffix and keep an override table for
   collisions (`update_team` PUT vs PATCH, `create_keyword` in `keywords` and
   `detection-keywords`, bare `update`/`delete` on numbering exceptions). Explicit
   `operation_id=` on routes, or unique function names, would remove the guesswork.
2. **Partial settings updates.** Consider `PATCH` semantics (or `exclude_unset` merging) on the
   `/settings/*` PUT routes so omitted fields keep their stored values.

Happy to take feedback or move any of the curated logic upstream if useful. MIT licensed.
