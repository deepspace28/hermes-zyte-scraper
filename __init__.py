"""Hermes plugin: hermes-zyte-scraper — Zyte extraction + intelligent spider generation."""

from . import schemas, tools
from .operations import (
    zyte_deploy,
    zyte_list_jobs,
    zyte_get_results,
    zyte_schedule,
)

def register(ctx) -> bool:
    # Existing extraction tool (with pagination support)
    ctx.register_tool(
        name="zyte_extract",
        toolset="zyte",
        schema=schemas.ZYTE_EXTRACT,
        handler=tools.zyte_extract,
        requires_env=["ZYTE_API_KEY"],
        description="Zyte-powered extraction with multi-page support",
        emoji="🕷️",
    )

    # The flagship tool: natural language → full production spider
    ctx.register_tool(
        name="zyte_build_spider",
        toolset="zyte",
        schema=schemas.ZYTE_BUILD_SPIDER,
        handler=tools.zyte_build_spider,
        requires_env=["ZYTE_API_KEY"],
        description="Generate complete Scrapy + Zyte projects from natural language",
        emoji="🕸️",
    )

    # === Operational Layer (Phase 4) ===
    ctx.register_tool(
        name="zyte_deploy",
        toolset="zyte",
        schema=schemas.ZYTE_DEPLOY,
        handler=zyte_deploy,
        requires_env=["ZYTE_API_KEY", "SCRAPY_CLOUD_API_KEY"],
        description="Deploy a generated spider project to Scrapy Cloud for continuous running",
        emoji="🚀",
    )

    ctx.register_tool(
        name="zyte_list_jobs",
        toolset="zyte",
        schema=schemas.ZYTE_LIST_JOBS,
        handler=zyte_list_jobs,
        requires_env=["SCRAPY_CLOUD_API_KEY"],
        description="List jobs on Scrapy Cloud",
        emoji="📋",
    )

    ctx.register_tool(
        name="zyte_get_results",
        toolset="zyte",
        schema=schemas.ZYTE_GET_RESULTS,
        handler=zyte_get_results,
        requires_env=["SCRAPY_CLOUD_API_KEY"],
        description="Fetch scraped items from a Scrapy Cloud job",
        emoji="📦",
    )

    ctx.register_tool(
        name="zyte_schedule",
        toolset="zyte",
        schema=schemas.ZYTE_SCHEDULE,
        handler=zyte_schedule,
        requires_env=["SCRAPY_CLOUD_API_KEY"],
        description="Schedule a spider to run continuously on Scrapy Cloud",
        emoji="⏰",
    )

    return True
