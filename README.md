# hermes-zyte-scraper

Production-grade Zyte + Scrapy Cloud integration for Hermes agents (v1.3.0).

Describe a scraping task in natural language, extract data via Zyte API, generate production Scrapy spiders, deploy to Scrapy Cloud, schedule runs, and retrieve stored results.

## Installation

```bash
git clone https://github.com/deepspace28/hermes-zyte-scraper.git ~/.hermes/plugins/hermes-zyte-scraper
cd ~/.hermes/plugins/hermes-zyte-scraper
pip install -r requirements.txt
hermes plugins enable hermes-zyte-scraper
```

Set credentials in `~/.hermes/.env`:

| Variable | Purpose |
|----------|---------|
| `ZYTE_API_KEY` | Zyte API extraction and spider runs |
| `SCRAPY_CLOUD_API_KEY` | Deploy, schedule, list jobs, fetch results |
| `SCRAPY_CLOUD_PROJECT_ID` | Numeric Scrapy Cloud project ID (e.g. `867424`) |

**Scrapy Cloud:** Also set `ZYTE_API_KEY` in your project's environment variables in the [Zyte dashboard](https://app.zyte.com).

## Tools

| Tool | When to use |
|------|-------------|
| `zyte_extract` | Quick one-off or moderate multi-page extraction (auto schema inference) |
| `zyte_build_spider` | Generate a full Scrapy + Zyte project (requires `start_url`) |
| `zyte_deploy` | Deploy generated project to Scrapy Cloud |
| `zyte_schedule` | Run spider once or on a cron schedule (uses `run.json` API) |
| `zyte_list_jobs` | Monitor Scrapy Cloud jobs |
| `zyte_get_results` | Pull items from Scrapy Cloud storage |

Load the workflow skill in Hermes: `skill_view("hermes-zyte-scraper:zyte-scraping")`

## zyte_extract highlights (v1.3.0)

- **Auto schema inference** — Indeed → `jobPostingNavigation`, Zillow/Amazon → `productList`
- **Multi-page pagination** — browserHtml + robust next-page detection
- **Sessions** — optional `session_id` for cookie/IP reuse
- **Custom attributes** — `custom_attributes="address,price,beds,baths"` per Zyte docs

## End-to-end example

```
# 1. Quick extraction (schema inferred from URL)
zyte_extract url="https://books.toscrape.com/" max_pages=5

# 2. Build a production spider
zyte_build_spider \
  description="Scrape book titles, prices, and URLs with pagination" \
  start_url="https://books.toscrape.com/" \
  spider_name="books-demo"

# 3. Deploy to Scrapy Cloud
zyte_deploy project_path="~/.hermes/spiders/books-demo"

# 4. Schedule a one-time run
zyte_schedule project_id="867424" spider="books-demo"

# 5. Monitor and fetch results
zyte_list_jobs project_id="867424"
zyte_get_results job_id="867424/books-demo/1"
```

Use `dry_run=true` on operational tools to validate without API calls.

## Battle testing

Recorded minimums: `tests/fixtures/battle_matrix_expected.json`

Run live matrix locally (requires `ZYTE_API_KEY`):

```bash
python scripts/run_battle_matrix.py
```

## Development

```bash
pip install -r requirements.txt pytest
python -m pytest tests/ -v
```

## Cost notes

Zyte charges per successful API response. Browser rendering, sessions, custom attributes, and large multi-page crawls increase cost. Set spending limits in the Zyte dashboard.