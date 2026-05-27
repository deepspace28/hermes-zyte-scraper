"""Tool schemas — now with native pagination support + spider generation."""

ZYTE_EXTRACT = {
    "name": "zyte_extract",
    "description": (
        "High-quality, resilient multi-page structured extraction using Zyte API (2026). "
        "Primary strategy uses productList (or other auto-extract types) + browserHtml fallback with robust custom HTML parsing. "
        "Multi-strategy pagination (Zyte nextPage hints + broad HTML link detection + URL param increment + optional actions). "
        "Strong general-purpose design that works on arbitrary/unknown sites (domain-specific enhancements are additive only). "
        "Supports cost/quality controls such as extractFrom, model pinning, geolocation, and custom attributes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Starting URL (list or detail page)"},
            "schema": {
                "type": "string",
                "description": "Primary extraction type: 'productList' (recommended default for generality), 'product', 'articleList', 'article', 'pageContent', etc. Navigation schemas (productNavigation etc.) are supported but not required — the implementation falls back gracefully.",
                "default": "productList"
            },
            "max_pages": {
                "type": "integer",
                "description": "Maximum pages to follow (default 1). Higher values are fine; for very large crawls prefer zyte_build_spider + Scrapy Cloud scheduling.",
                "default": 5
            },
            "extract_from": {
                "type": "string",
                "description": "Zyte extractFrom option: 'browserHtml' (default, high quality), 'browserHtmlOnly', or 'httpResponseBody' (faster/cheaper).",
                "default": "browserHtml"
            },
            "geolocation": {
                "type": "string",
                "description": "Optional ISO country code (e.g. 'US', 'DE') for request geolocation. Zyte picks sensible default per site.",
                "default": ""
            },
        },
        "required": ["url"],
    },
}

ZYTE_BUILD_SPIDER = {
    "name": "zyte_build_spider",
    "description": (
        "Generates a complete, production-ready Scrapy project using zyte-spider-templates. "
        "The agent can create high-quality, paginating spiders for Amazon, Zillow, Indeed, e-commerce, "
        "job boards, etc. The generated project is saved to ~/.hermes/spiders/<name>/ and is immediately runnable."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Natural language description of what to scrape. Example: "
                              "'Build a spider for Amazon wireless headphones that follows pagination and extracts name, price, rating, url, availability, ASIN'"
            },
            "spider_name": {
                "type": "string",
                "description": "Optional custom name for the spider/project (will be slugified). If not provided, one will be generated from the description.",
                "default": ""
            },
        },
        "required": ["description"],
    },
}

# =============================================================================
# Andrej Karpathy-style Autoresearch (no GPU dependency)
# =============================================================================

AUTORESEARCH = {
    "name": "autoresearch",
    "description": (
        "Andrej Karpathy-style autonomous research agent. "
        "Given a research question or topic, it performs multi-step research: "
        "breaks down the problem, uses high-quality web scraping (Zyte), gathers information, "
        "synthesizes insights, generates hypotheses, and produces a research report. "
        "Inspired by Karpathy's vision of AI that can do real research autonomously. "
        "Does NOT require local GPUs — leverages the host Hermes LLM."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The research question or topic. Example: "
                              "'What are the latest techniques in test-time compute for LLMs?' or "
                              "'Deep research on effective context length extension methods beyond 128k'"
            },
            "depth": {
                "type": "integer",
                "description": "How deep the research should go (1-5). Higher = more iterations, more sources, deeper analysis. Default 3.",
                "default": 3
            },
            "focus": {
                "type": "string",
                "description": "Optional focus area: 'papers', 'practical', 'recent', 'comprehensive'",
                "default": "comprehensive"
            },
        },
        "required": ["query"],
    },
}

# =============================================================================
# Operational Layer — Scrapy Cloud Management (Phase 4)
# =============================================================================

ZYTE_DEPLOY = {
    "name": "zyte_deploy",
    "description": (
        "Deploy a spider project (generated by zyte_build_spider) to Scrapy Cloud. "
        "This is the main entry point for taking a locally generated spider and making it run continuously."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Path to the Scrapy project folder (e.g. ~/.hermes/spiders/my_amazon_spider)"
            },
            "project_name": {
                "type": "string",
                "description": "Optional custom name for the project on Scrapy Cloud. If not provided, the folder name is used.",
                "default": ""
            },
        },
        "required": ["project_path"],
    },
}

ZYTE_LIST_JOBS = {
    "name": "zyte_list_jobs",
    "description": "List jobs for a deployed spider or project on Scrapy Cloud. Useful for monitoring continuous runs.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Scrapy Cloud project ID (or name). If omitted, uses the default configured project."
            },
            "spider": {
                "type": "string",
                "description": "Optional spider name to filter jobs.",
                "default": ""
            },
            "state": {
                "type": "string",
                "description": "Filter by job state: pending, running, finished, or all.",
                "default": "all"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of jobs to return.",
                "default": 20
            },
        },
    },
}

ZYTE_GET_RESULTS = {
    "name": "zyte_get_results",
    "description": "Fetch scraped items from a completed or running job on Scrapy Cloud.",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The full job ID on Scrapy Cloud (format: <project_id>/<spider_id>/<job_id>)"
            },
            "format": {
                "type": "string",
                "description": "Output format: json, jsonlines, csv, or xml.",
                "default": "jsonlines"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of items to return (0 = all available).",
                "default": 0
            },
        },
        "required": ["job_id"],
    },
}

ZYTE_SCHEDULE = {
    "name": "zyte_schedule",
    "description": "Schedule a spider to run on Scrapy Cloud (one-time or recurring via cron). Supports tags and job_settings overrides.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Scrapy Cloud project ID or name."
            },
            "spider": {
                "type": "string",
                "description": "Name of the spider to schedule."
            },
            "schedule": {
                "type": "string",
                "description": "Cron expression for recurring runs (e.g. '0 */6 * * *'). Leave empty for a one-time run.",
                "default": ""
            },
            "units": {
                "type": "integer",
                "description": "Number of Scrapy Cloud units to use for the job.",
                "default": 1
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags to attach to the scheduled job(s) for filtering/monitoring.",
                "default": []
            },
            "job_settings": {
                "type": "object",
                "description": "Optional Scrapy settings overrides for the job (merged with project/spider settings).",
                "default": {}
            },
        },
        "required": ["project_id", "spider"],
    },
}
