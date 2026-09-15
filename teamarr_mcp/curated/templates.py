from __future__ import annotations

from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from teamarr_mcp.api import TeamarrApi
from teamarr_mcp.curated import ServerContext

UPDATE_KEYS_FALLBACK = [
    "name",
    "sport",
    "league",
    "title_format",
    "subtitle_template",
    "description_template",
    "program_art_url",
    "game_duration_mode",
    "game_duration_override",
    "xmltv_flags",
    "xmltv_video",
    "xmltv_categories",
    "xmltv_filler_categories",
    "pregame_enabled",
    "pregame_fallback",
    "postgame_enabled",
    "postgame_fallback",
    "postgame_conditional",
    "idle_enabled",
    "idle_content",
    "idle_conditional",
    "idle_offseason",
    "pregame_conditional_rows",
    "postgame_conditional_rows",
    "idle_conditional_rows",
    "conditional_descriptions",
    "event_channel_name",
    "event_channel_logo_url",
]

Section = Literal["pregame", "postgame"]
Field = Literal["title", "subtitle", "description", "description_fallback", "art_url"]


def update_keys(spec: dict) -> list[str]:
    schemas = spec.get("components", {}).get("schemas", {})
    props = schemas.get("TemplateUpdate", {}).get("properties")
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
        chosen = [{"id": i} for i in template_ids] if template_ids is not None else summaries
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
