# hermes-zyte-scraper

**Production-grade Zyte + Scrapy integration plugin for Hermes agents.**

Enable Hermes to help users solve real web scraping problems: describe a scraping need in natural language → generate a high-quality, general-purpose Scrapy spider using Zyte → deploy it to Scrapy Cloud → schedule continuous runs → monitor jobs → retrieve structured results.

The plugin is deliberately **general-purpose** (works for arbitrary sites and queries, not just detectable niches like Zillow or Amazon) and follows 2026 Zyte best practices (Zyte API client, browserHtml + automatic extraction, multi-strategy pagination, sessions, actions, cost awareness).

---

## Installation & Enablement

```bash
# The plugin lives at ~/.hermes/plugins/hermes-zyte-scraper/
hermes plugins enable hermes-zyte-scraper
```

You will be prompted for a `ZYTE_API_KEY` (and optionally a Scrapy Cloud API key) via the `requires_env` mechanism if not already present. Values are stored in `~/.hermes/.env`.

After enabling, the tools appear in the agent's tool list and the model can use them immediately.

---

## Public Tools

### 1. zyte_extract

High-quality, multi-page, general-purpose extraction powered by Zyte API.

**Key capabilities (mapped to Zyte contracts):**
- Primary: `productList` (or other auto-extract types) with configurable `extractFrom` (`browserHtml` default for quality, `httpResponseBody` for cost).
- Fallback + enrichment: `browserHtml` + robust custom HTML parsing.
- Pagination: Zyte `nextPage` hints + multi-strategy HTML link finding (CSS/regex) + page parameter increment + optional browser `actions`.
- Deduplication, quality scoring, and recommendations.
- Optional `max_pages`, `geolocation`, custom attributes, model pinning.

**When to use:** One-off or moderate-depth scraping of lists/details on unknown sites. Returns structured JSON + raw artifacts when requested.

See schemas for full parameter contract.

### 2. zyte_build_spider

Describe a scraping task in natural language → receive a complete, production-ready Scrapy + `scrapy-zyte-api` project in `~/.hermes/spiders/<name>/`.

**Output includes:**
- `scrapy.cfg`, `settings.py` (Zyte middleware, proper Cloud config)
- `items.py`
- High-quality spider (ZyteApiSpider subclass) with dual-strategy extraction, strong general-purpose `_extract_items_from_html`, multi-strategy `_find_next_page` (including actions support), zpid-style dedup, domain hooks (additive only), logging, and SC-ready metadata.
- `README.md` with local run instructions + full shub deploy + schedule steps.

The generated spider is designed for **any site** (strong fallbacks + additive domain intelligence) and follows the exact patterns validated in the Zyte documentation study (browser + auto-extract combinations, actions for hard navigation, sessions for state, etc.).

**Production features in generated projects:**
- Cost notes and `extractFrom` / model pinning options.
- Session and geolocation examples.
- Proper tagging and `jobId` usage for observability on Scrapy Cloud.

### 3–6. Operational Layer (Scrapy Cloud Lifecycle)

- `zyte_deploy` — Package and deploy the generated project via shub.
- `zyte_schedule` — Schedule one-off or recurring runs (supports spider name or ID, project name resolution, tags, units, settings overrides).
- `zyte_list_jobs` — List jobs with rich filters (spider name, state, tags). Supports pagination and name-based resolution.
- `zyte_get_results` — Retrieve items (streaming `.jl` preferred, csv/json options, pagination via storage API).

**Implementation notes (from Scrapy Cloud reference study):**
- Uses separate Scrapy Cloud API key (distinct from Zyte API key).
- Correct host-specific pagination (`app.zyte.com` vs `storage.zyte.com`).
- Name resolution helpers (projects/spiders by human name).
- Full support for tags, job_settings, priority, etc.

These tools give Hermes agents end-to-end control: generate → deploy → run continuously → monitor → pull fresh data.

### 7. autoresearch (Karpathy-style)

Autonomous research agent (propose → experiment → measure → keep/discard). Can be used for general research or for self-improvement of this plugin (tracks defined in private `internal/research/program.md`).

**Important:** All autoresearch artifacts (`program.md`, session logs, dashboard) are **private** and live only in `internal/research/`. They are never published.

---

## Architecture & Design Decisions (Grounded in Official Docs)

### Zyte API (2026)
- Single endpoint: `POST https://api.zyte.com/v1/extract` (Basic auth with Zyte key).
- Official `zyte_api` client used everywhere.
- Strict mutual-exclusion rules respected (one primary auto-extract type per call; no mixing `httpResponseBody` + browser-only fields).
- `extractFrom`, model pinning, actions (60s limit), sessions (client- and server-managed), geolocation, custom attributes, networkCapture — all first-class in tools and generated code.
- Error model fully internalized: 520 ban-retry (free), rate limits (clients auto-retry with backoff), 4xx contract violations, successful responses even on partial action/extract failure (`metadata.probability`, per-action status).

### Scrapy Cloud
- Separate API key.
- Jobs API (`app.zyte.com`) for scheduling/listing/updating/stopping.
- Storage API (`storage.zyte.com`) for items/logs (multiple formats, pagination subtleties handled).
- `python-scrapinghub` + direct HTTP used as appropriate in `operations.py`.

### Hermes Plugin Contract (2026 patterns)
- Modern `ctx.register_tool(schema, handler)` + `ctx.register_hook` / `ctx.register_command` / `ctx.register_cli_command` / `ctx.dispatch_tool` / `ctx.register_skill`.
- `plugin.yaml` manifest with `provides_tools`, `requires_env`, version, etc.
- Handlers: `def handler(args: dict, **kwargs) -> str` — **always** return JSON string, never raise, accept `**kwargs`.
- Schemas are precise, descriptive (LLM uses the `description` heavily), and live in `schemas.py`.
- `pre_llm_call` hooks can inject context; other hooks are observers.
- Opt-in via `plugins.enabled`; grandfathering and interactive management supported.

The plugin follows these contracts exactly (no legacy `.tools/hooks` patterns).

### Generality Principle
Domain detection is **additive only**. The core extraction and pagination logic is robust and domain-agnostic (broad regex/CSS, Zyte hints + fallbacks, deduplication). This matches real-world Zyte usage for arbitrary sites.

---

## Production Considerations

- **Cost:** Only successful responses are charged. Browser + actions + auto-extract + custom attrs ("generate") + residential IPs + extended geolocations drive cost. The plugin surfaces `extractFrom`, model pinning, and cost-optimized paths. Users should set spending limits.
- **Reliability:** Official clients handle rate limits and basic retries. Plugin adds multi-strategy fallbacks and operational resilience.
- **Observability:** Generated spiders + operational tools use tags, `jobId`, `echoData`. Combine with Scrapy Cloud UI + Zyte stats.
- **Stateful crawling:** Use sessions (client-managed UUID recommended for simplicity) + actions.
- **Large results:** `zyte_get_results` streams `.jl`; prefer it for high volume.

See the internal Zyte study (`internal/research/zyte-documentation-systematic-study.md`) for exhaustive subsection mapping.

---

## Project Layout (Current)

```
hermes-zyte-scraper/
├── plugin.yaml
├── __init__.py          # register(ctx) — wires everything
├── schemas.py           # Precise tool schemas (LLM-visible)
├── tools.py             # Thin handlers (delegate to operations + extract logic)
├── operations.py        # ScrapyCloudClient (deploy/schedule/list/get_results + resolution)
├── autoresearch.py      # Research agent implementation
├── templates/
│   └── high_quality_spider.py.template
├── README.md
└── internal/
    └── research/        # PRIVATE — program.md, logs, Zyte study, etc. (never publish)
```

Generated user projects land in `~/.hermes/spiders/<name>/`.

---

## Development & Self-Improvement

This plugin was developed with parallel Karpathy-style autoresearch across four tracks (spider quality, extraction robustness, autoresearch tooling, operational layer). The research organization lives privately in `internal/research/program.md`.

To iterate: use the `autoresearch` tool (with appropriate track context) or manual experiments against real Zyte targets. Never publish research artifacts.

A complete record of the development process, all major decisions, studies, code changes, and research campaigns is available internally at:
`internal/docs/FULL_DEVELOPMENT_HISTORY.md`

---

## Status

As of the completion of the systematic Zyte + Hermes documentation studies (April 2026), the plugin implements the core vision at high quality:

- Accurate mapping to current Zyte API / Scrapy Cloud contracts.
- Correct modern Hermes plugin registration and handler discipline.
- General-purpose spider generation and extraction that works for arbitrary sites.
- Functional operational layer with name resolution and pagination.

Further production hardening (full custom attributes + sessions exposure, expanded schedule CRUD, richer cost tooling, more auto-extract types in the generator) is tracked via the private research process.

---

**References (for accuracy):**
- All Zyte sections studied: main index, Zyte API (get-started, usage/http, browser, extract, reference, features, errors, pricing, custom-attributes), Scrapy Cloud (get-started + full HTTP API reference including jobs + storage pagination).
- Hermes guides: full "Build a Hermes Plugin" (step-by-step + specialized types + hooks + distribution) and "Plugins" (discovery, opt-in model, management UI, pluggable interfaces table).

For questions or to enable advanced Zyte features in a generated spider, simply describe the requirement to Hermes — the tools are designed for exactly that.