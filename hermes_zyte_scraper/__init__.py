"""Hermes plugin: hermes-zyte-scraper — Zyte extraction + spider generation + Scrapy Cloud."""

from pathlib import Path

from . import schemas, tools
from .operations import (
    zyte_deploy,
    zyte_get_results,
    zyte_list_jobs,
    zyte_schedule,
)

_SCRAPE_HINTS = ("scrape", "spider", "zyte", "crawl", "extract", "scrapy cloud")


def _on_pre_llm_call(*, user_message: str = "", **kwargs):
    text = (user_message or "").lower()
    if any(hint in text for hint in _SCRAPE_HINTS):
        return {
            "context": (
                "The hermes-zyte-scraper plugin is enabled. Use the zyte toolset: "
                "zyte_extract for quick scrapes; zyte_build_spider (requires start_url) "
                "for production spiders; then zyte_deploy, zyte_schedule, "
                "zyte_list_jobs, zyte_get_results for Scrapy Cloud storage."
            )
        }
    return None


def register(ctx) -> bool:
    ctx.register_tool(
        name="zyte_extract",
        toolset="zyte",
        schema=schemas.ZYTE_EXTRACT,
        handler=tools.zyte_extract,
        requires_env=["ZYTE_API_KEY"],
        description="Zyte-powered extraction with multi-page support",
        emoji="🕷️",
    )

    ctx.register_tool(
        name="zyte_build_spider",
        toolset="zyte",
        schema=schemas.ZYTE_BUILD_SPIDER,
        handler=tools.zyte_build_spider,
        requires_env=["ZYTE_API_KEY"],
        description="Generate complete Scrapy + Zyte projects from natural language",
        emoji="🕸️",
    )

    ctx.register_tool(
        name="zyte_deploy",
        toolset="zyte",
        schema=schemas.ZYTE_DEPLOY,
        handler=zyte_deploy,
        requires_env=["ZYTE_API_KEY", "SCRAPY_CLOUD_API_KEY"],
        description="Deploy a generated spider project to Scrapy Cloud",
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
        description="Schedule a spider on Scrapy Cloud",
        emoji="⏰",
    )

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)

    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    return True
