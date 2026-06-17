"""Tool schemas for the hermes-zyte-scraper plugin."""

ZYTE_EXTRACT = {
    "name": "zyte_extract",
    "description": (
        "High-quality multi-page structured extraction using Zyte API. "
        "Uses auto-extract first, then browserHtml fallback. "
        "Best for one-off or moderate-depth scraping. "
        "For large ongoing crawls, use zyte_build_spider + Scrapy Cloud."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Starting URL (list or detail page)"},
            "schema": {
                "type": "string",
                "description": (
                    "Zyte auto-extract type: productList, jobPostingNavigation, "
                    "articleList, pageContent, or 'auto' (inferred from URL)."
                ),
                "default": "auto",
            },
            "auto_schema": {
                "type": "boolean",
                "description": "When true, infer schema from URL (Indeed→jobs, Zillow→listings).",
                "default": True,
            },
            "custom_attributes": {
                "type": "string",
                "description": (
                    "Comma-separated fields or JSON schema for Zyte customAttributes "
                    "(e.g. 'address,price,beds,baths')."
                ),
                "default": "",
            },
            "custom_attributes_method": {
                "type": "string",
                "description": "customAttributes method: extract (cheaper) or generate.",
                "default": "extract",
            },
            "session_id": {
                "type": "string",
                "description": "Optional Zyte session UUID for cookie/IP reuse across pages.",
                "default": "",
            },
            "max_pages": {
                "type": "integer",
                "description": "Maximum pages to follow (default 5).",
                "default": 5,
            },
            "extract_from": {
                "type": "string",
                "description": "Zyte extractFrom: browserHtml (quality) or httpResponseBody (cheaper).",
                "default": "browserHtml",
            },
            "geolocation": {
                "type": "string",
                "description": "Optional ISO country code (e.g. US, DE).",
                "default": "",
            },
        },
        "required": ["url"],
    },
}

ZYTE_BUILD_SPIDER = {
    "name": "zyte_build_spider",
    "description": (
        "Generate a complete Scrapy + Zyte project from natural language. "
        "Saves to ~/.hermes/spiders/<name>/ and is ready for local run or Scrapy Cloud deploy."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": (
                    "What to scrape and which fields to extract. "
                    "Example: 'Zillow Seattle homes: address, price, beds, baths, sqft, url'"
                ),
            },
            "start_url": {
                "type": "string",
                "description": "Required starting URL for the spider.",
            },
            "spider_name": {
                "type": "string",
                "description": "Optional custom project/spider name (slugified).",
                "default": "",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Overwrite existing project directory if it exists.",
                "default": False,
            },
        },
        "required": ["description", "start_url"],
    },
}

ZYTE_DEPLOY = {
    "name": "zyte_deploy",
    "description": "Deploy a generated spider project to Scrapy Cloud via shub.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Path to the Scrapy project (e.g. ~/.hermes/spiders/my-spider)",
            },
            "project_name": {
                "type": "string",
                "description": "Optional Scrapy Cloud project name override.",
                "default": "",
            },
            "dry_run": {
                "type": "boolean",
                "description": "Log deploy steps without executing shub.",
                "default": False,
            },
        },
        "required": ["project_path"],
    },
}

ZYTE_LIST_JOBS = {
    "name": "zyte_list_jobs",
    "description": "List jobs for a Scrapy Cloud project.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Scrapy Cloud project ID or name.",
            },
            "spider": {
                "type": "string",
                "description": "Optional spider name filter.",
                "default": "",
            },
            "state": {
                "type": "string",
                "description": "pending, running, finished, or all.",
                "default": "all",
            },
            "limit": {"type": "integer", "description": "Max jobs to return.", "default": 20},
            "offset": {"type": "integer", "description": "Pagination offset.", "default": 0},
            "dry_run": {
                "type": "boolean",
                "description": "Return without calling Scrapy Cloud API.",
                "default": False,
            },
        },
        "required": ["project_id"],
    },
}

ZYTE_GET_RESULTS = {
    "name": "zyte_get_results",
    "description": "Fetch scraped items from a Scrapy Cloud job (storage.zyte.com).",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "Job ID: <project_id>/<spider_id>/<job_id>",
            },
            "format": {
                "type": "string",
                "description": "jsonlines, json, csv, or xml.",
                "default": "jsonlines",
            },
            "limit": {
                "type": "integer",
                "description": "Max items (0 = all available).",
                "default": 0,
            },
            "offset": {"type": "integer", "description": "Pagination offset.", "default": 0},
            "dry_run": {
                "type": "boolean",
                "description": "Return without calling storage API.",
                "default": False,
            },
        },
        "required": ["job_id"],
    },
}

ZYTE_SCHEDULE = {
    "name": "zyte_schedule",
    "description": "Schedule a spider on Scrapy Cloud (one-time or cron).",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Scrapy Cloud numeric project ID (e.g. 867424).",
            },
            "priority": {
                "type": "integer",
                "description": "Job priority 0-4 (default 2).",
                "default": 2,
            },
            "spider": {"type": "string", "description": "Spider name to run."},
            "schedule": {
                "type": "string",
                "description": "Cron expression for recurring runs. Empty = one-time.",
                "default": "",
            },
            "units": {"type": "integer", "description": "Scrapy Cloud units.", "default": 1},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional job tags.",
                "default": [],
            },
            "job_settings": {
                "type": "object",
                "description": "Optional Scrapy settings overrides.",
                "default": {},
            },
            "dry_run": {
                "type": "boolean",
                "description": "Log schedule without calling API.",
                "default": False,
            },
        },
        "required": ["project_id", "spider"],
    },
}
