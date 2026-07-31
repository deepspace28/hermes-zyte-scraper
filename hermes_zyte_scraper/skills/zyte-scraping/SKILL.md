---
name: zyte-scraping
description: Production Zyte scraping workflow for Hermes — extract, build spiders, deploy to Scrapy Cloud, retrieve stored results.
---

# Zyte Scraping Workflow

Use the `zyte` toolset from the hermes-zyte-scraper plugin.

## Quick scrape (one-off)

Use `zyte_extract` when the user wants data from a URL without a persistent crawler.

Required: `url`
Optional: `max_pages`, `schema` (or `auto`), `auto_schema`, `extract_from`, `geolocation`, `session_id`, `custom_attributes`

Schema is auto-inferred from URL when `auto_schema=true` (Indeed→jobs, Zillow→listings).

If extraction quality is low, recommend `zyte_build_spider` for a custom spider.

## Production scrape (ongoing / large)

1. `zyte_build_spider` — requires `description` and `start_url`
2. `zyte_deploy` — deploy project from `~/.hermes/spiders/<name>/`
3. `zyte_schedule` — run once or on a cron schedule
4. `zyte_list_jobs` — monitor job status
5. `zyte_get_results` — pull items from Scrapy Cloud storage

## Environment

- `ZYTE_API_KEY` — required for extraction and spider runs (also set in Scrapy Cloud project env)
- `SCRAPY_CLOUD_API_KEY` — required for deploy, schedule, list, results
- `SCRAPY_CLOUD_PROJECT_ID` — numeric project ID for schedule/list (e.g. `867424`)

## Cost awareness

Zyte charges per successful API response. Browser rendering and multi-page crawls add cost. Warn users on large runs and suggest Scrapy Cloud for scheduled production workloads.

## Dry run

Operational tools support `dry_run=true` to validate arguments without hitting Scrapy Cloud APIs.
