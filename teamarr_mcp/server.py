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
    log.info(
        "Using %s OpenAPI spec (Teamarr %s, %d operations)",
        loaded.source,
        loaded.version,
        loaded.operation_count,
    )

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
    generated = len(await mcp.list_tools())
    ctx = ServerContext(settings=settings, loaded=loaded, generated_tool_count=generated)
    register_all(mcp, TeamarrApi(client, settings.url), ctx)
    log.info("Registered %d generated + %d curated tools", generated, len(ctx.curated_tool_names))
    return mcp


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
    logging.basicConfig(
        level=settings.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(serve(settings))


async def serve(settings: Settings) -> None:
    """Build and serve on ONE event loop.

    The shared httpx2 client pools the connection used to fetch /openapi.json during
    build_server(). Serving from a second loop (asyncio.run + mcp.run) made the first tool
    call reuse that socket and fail with "Event loop is closed".
    """
    mcp = await build_server(settings)
    if settings.transport == "stdio":
        await mcp.run_async(transport="stdio", show_banner=False)
    else:
        await mcp.run_async(
            transport="http",
            host=settings.host,
            port=settings.port,
            path="/mcp",
            show_banner=False,
        )
