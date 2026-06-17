# hermes-zyte-scraper

Production-grade Zyte + Scrapy Cloud integration for Hermes agents.

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

## Tools

| Tool | When to use |
|------|-------------|
| `zyte_extract` | Quick one-off or moderate multi-page extraction |
| `zyte_build_spider` | Generate a full Scrapy + Zyte project (requires `start_url`) |
| `zyte_deploy` | Deploy generated project to Scrapy Cloud |
| `zyte_schedule` | Run spider once or on a cron schedule |
| `zyte_list_jobs` | Monitor Scrapy Cloud jobs |
| `zyte_get_results` | Pull items from Scrapy Cloud storage |

Load the workflow skill in Hermes: `skill_view("hermes-zyte-scraper:zyte-scraping")`

## End-to-end example

```
# 1. Quick extraction
zyte_extract url="https://books.toscrape.com/" max_pages=2

# 2. Build a production spider
zyte_build_spider \
  description="Scrape book titles, prices, and URLs with pagination" \
  start_url="https://books.toscrape.com/" \
  spider_name="books-demo"

# 3. Deploy to Scrapy Cloud
zyte_deploy project_path="~/.hermes/spiders/books-demo"

# 4. Schedule a one-time run
zyte_schedule project_id="books-demo" spider="books-demo"

# 5. Monitor and fetch results
zyte_list_jobs project_id="books-demo"
zyte_get_results job_id="<project>/<spider>/<job>"
```

Use `dry_run=true` on operational tools to validate without API calls.

## Project layout

```
hermes-zyte-scraper/
├── plugin.yaml
├── __init__.py
├── schemas.py
├── tools.py
├── operations.py
├── requirements.txt
├── skills/zyte-scraping/SKILL.md
├── templates/high_quality_spider.py.template
└── tests/test_tools.py
```

Generated spiders are written to `~/.hermes/spiders/<name>/`.

## Development

```bash
pip install -r requirements.txt pytest
pytest tests/ -v
```

## Cost notes

Zyte charges per successful API response. Browser rendering, actions, and large multi-page crawls increase cost. Set spending limits in the Zyte dashboard.
