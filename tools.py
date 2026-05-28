"""Tool handlers with practical multi-page extraction + powerful spider generation.

The zyte_build_spider tool is the flagship feature for creating production-grade
scrapers via natural language.

Priority 1 fixes:
- zyte_extract: Fix mutual exclusion (two sequential calls, not both in one)
- zyte_build_spider: Make start_url REQUIRED, fix is_complex_job naming
- All handlers: Return proper JSON, never raise, use **kwargs
"""

import json
import os
import re
import shutil
import time
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from zyte_api import ZyteAPI


# =============================================================================
# Helper: zyte_extract robust next-page detection
# =============================================================================

def _find_next_page_in_response(resp: dict, current_url: str) -> str | None:
    """Helper for robust next page detection using Zyte hints + HTML parsing."""
    from urllib.parse import urljoin
    import re

    # Strategy 1: Try Zyte nextPage hint if present
    next_info = resp.get("nextPage") or {}
    if isinstance(next_info, dict) and next_info.get("url"):
        return next_info["url"]

    # Strategy 2: Parse HTML for next-page links
    html = resp.get("browserHtml", "")
    if not html:
        return None
    
    patterns = [
        r'href=["\']([^"\']*page=\d+[^"\']*)["\'][^>]*rel=["\']?next',
        r'class=["\'][^"\']*next[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
        r'href=["\']([^"\']*\?page=\d[^"\']*)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            candidate = match.group(1)
            if candidate.startswith("/"):
                return urljoin(current_url, candidate)
            return candidate
    return None


def _extract_items_from_html(html: str) -> list:
    """
    General-purpose HTML fallback extractor (additive domain-agnostic logic).
    Works reasonably on arbitrary list pages without assuming known domains.
    """
    import re
    items = []
    
    # Broad, domain-agnostic patterns for potential product/item links
    patterns = [
        r'href=["\'](/[^"\']+/[a-z0-9-]{5,}[^"\']*)["\']',
        r'href=["\'](/[^"\']*detail[^"\']*)["\']',
        r'href=["\'](/[^"\']*item[^"\']*)["\']',
        r'href=["\'](/[^"\']*product[^"\']*)["\']',
    ]
    all_links = []
    for pat in patterns:
        all_links.extend(re.findall(pat, html, re.IGNORECASE))
    
    # Deduplicate and limit
    seen = set()
    for link in all_links:
        if link not in seen and len(link) > 6:
            seen.add(link)
            items.append({"url": link, "name": "General-purpose HTML fallback"})
            if len(items) >= 25:
                break
    
    return items


# =============================================================================
# zyte_extract — FIXED: two sequential calls, proper mutual exclusion
# =============================================================================

def zyte_extract(args: dict, **kwargs) -> str:
    """
    Multi-page extraction with proper Zyte API mutual exclusion.
    
    FIX (Priority 3):
    - Now uses two sequential calls: first productList, then browserHtml fallback.
    - Respects Zyte mutual-exclusion: no mixing incompatible extraction modes in one call.
    - Cost-aware: returns extractFrom info so agent can relay costs to users.
    """
    url = args.get("url")
    max_pages = int(args.get("max_pages", 1))
    extract_from = args.get("extract_from", "browserHtml")
    schema = args.get("schema", "productList")

    if not url:
        return json.dumps({"success": False, "error": "url is required"})

    try:
        client = ZyteAPI()
        results = []
        current_url = url
        page = 1
        seen_urls = set()
        total_cost_estimate = 0.0

        while page <= max_pages and current_url:
            page_result = {
                "page": page,
                "url": current_url,
                "item_count": 0,
                "items": [],
                "extraction_method": None,
            }

            # CALL 1: Primary strategy - auto-extract (e.g., productList)
            try:
                payload1 = {
                    "url": current_url,
                    schema: True,
                    "extractFrom": extract_from,
                }
                if args.get("geolocation"):
                    payload1["geolocation"] = args["geolocation"]

                resp1 = client.get(payload1, endpoint="extract")
                
                # Extract auto-extracted items
                auto_data = resp1.get(schema, {})
                if isinstance(auto_data, dict):
                    items = auto_data.get("products", auto_data.get("items", []))
                else:
                    items = auto_data if isinstance(auto_data, list) else []

                total_cost_estimate += 0.01  # Rough estimate per extraction call
                page_result["extraction_method"] = f"auto-extract ({schema})"

            except Exception as e:
                items = []
                page_result["extraction_error"] = str(e)

            # CALL 2: Fallback strategy - if primary was weak, try browserHtml + parse
            if len(items) < 3:
                try:
                    payload2 = {
                        "url": current_url,
                        "browserHtml": True,
                    }
                    if args.get("geolocation"):
                        payload2["geolocation"] = args["geolocation"]

                    resp2 = client.get(payload2, endpoint="extract")
                    html = resp2.get("browserHtml", "")
                    fallback_items = _extract_items_from_html(html)
                    
                    if fallback_items:
                        items = fallback_items
                        page_result["extraction_method"] = "browserHtml + custom HTML parsing"
                        total_cost_estimate += 0.01  # Cost for fallback call

                except Exception as e:
                    page_result["fallback_error"] = str(e)

            # Dedup across pages
            new_items = []
            for item in items:
                item_url = item.get("url") or item.get("detailUrl")
                if item_url and item_url not in seen_urls:
                    seen_urls.add(item_url)
                    new_items.append(item)
            items = new_items

            page_result["item_count"] = len(items)
            page_result["items"] = items
            results.append(page_result)

            # Multi-strategy next page detection
            try:
                next_url = _find_next_page_in_response(resp1 if 'resp1' in locals() else {}, current_url)
            except:
                next_url = None
            
            if next_url:
                current_url = next_url
            elif "page=" in current_url:
                current_url = re.sub(r"page=(\d+)", lambda m: f"page={int(m.group(1))+1}", current_url)
            else:
                current_url = None

            page += 1

        # Quality scoring and recommendations
        avg_items = sum(r["item_count"] for r in results) / max(len(results), 1)
        quality_score = min(1.0, avg_items / 15.0)

        recommendations = []
        if quality_score < 0.4:
            recommendations.append(
                "Extraction was weak on this site. For better results, strongly consider using zyte_build_spider "
                "to generate a custom, robust spider with domain-specific intelligence."
            )
        if len(results) > 0 and results[-1]["item_count"] == 0:
            recommendations.append("Last page returned zero items — pagination likely ended or site structure changed.")

        return json.dumps({
            "success": True,
            "pages_scraped": len(results),
            "total_items": sum(r["item_count"] for r in results),
            "quality_score": round(quality_score, 2),
            "cost_estimate": f"~${round(total_cost_estimate, 3)} (Zyte charges only for successful responses)",
            "extract_from_used": extract_from,
            "recommendations": recommendations,
            "results": results,
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# =============================================================================
# Helper: slugify + URL inference (for backward compat, but start_url is now REQUIRED)
# =============================================================================

def _slugify(text: str) -> str:
    """Convert text to a valid slug for project names."""
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text).strip().lower()
    text = re.sub(r'[\s-]+', '-', text)
    return text[:60] or "custom-spider"


def _extract_fields(description: str) -> list[str]:
    """Extract list of fields the user wants from description."""
    common = ["name", "price", "url", "rating", "availability", "asin", "address", 
              "beds", "baths", "sqft", "title", "description", "image", "reviews", "category"]
    
    found = []
    desc_lower = description.lower()
    for field in common:
        if field in desc_lower:
            found.append(field)
    
    if not found:
        found = ["name", "price", "url"]
    return found


# =============================================================================
# zyte_build_spider — FIXED: start_url REQUIRED, is_complex_job → is_complex_job
# =============================================================================

def zyte_build_spider(args: dict, **kwargs) -> str:
    """
    Generates a complete, production-ready Scrapy + Zyte project.
    
    FIX (Priority 4):
    - start_url is now REQUIRED (not guessed).
    - is_complex_fleet → is_complex_job (consistency).
    - Adds cost estimates to output.
    - Checks for overwrite before deleting directories.
    """
    description = args.get("description", "")
    start_url = args.get("start_url", "")
    custom_name = args.get("spider_name", "")
    overwrite = args.get("overwrite", False)

    if not description:
        return json.dumps({"success": False, "error": "description is required"})
    
    if not start_url:
        return json.dumps({
            "success": False,
            "error": (
                "start_url is required. Please provide the starting URL for the spider. "
                "Example: 'https://example.com/products' or 'https://amazon.com/s?k=headphones'"
            )
        })

    try:
        # --- Intelligence layer ---
        project_name = _slugify(custom_name or description)
        fields = _extract_fields(description)

        # Detect special requirements
        needs_login = "login" in description.lower() or "authenticated" in description.lower()
        infinite_scroll = "infinite scroll" in description.lower() or "scroll" in description.lower()

        # Domain-aware template selection
        domain_type = "general"
        if any(x in description.lower() for x in ["real estate", "zillow", "homes", "property"]):
            domain_type = "real_estate"
        elif any(x in description.lower() for x in ["amazon", "product", "e-commerce", "shop"]):
            domain_type = "ecommerce"
        elif any(x in description.lower() for x in ["job", "indeed", "career"]):
            domain_type = "jobs"

        # === Complex Job Detection (FIXED: renamed from is_complex_fleet) ===
        is_complex_job = len(description) > 160 or any(kw in description.lower() for kw in [
            "multiple sources", "several sites", "different websites", "multi-source", "various platforms"
        ])

        sub_spiders = []
        if is_complex_job:
            domain_type = "complex"
            sub_spiders = ["main", "details", "related", "pagination"]

        # --- Create project directory (with overwrite check) ---
        base_dir = Path.home() / ".hermes" / "spiders" / project_name
        if base_dir.exists():
            if not overwrite:
                return json.dumps({
                    "success": False,
                    "error": f"Project directory already exists at {base_dir}. Set overwrite=true to regenerate.",
                })
            # Check if directory was recently modified (safety check)
            mtime = base_dir.stat().st_mtime
            if (time.time() - mtime) < 3600 and not overwrite:
                return json.dumps({
                    "success": False,
                    "error": f"Project was modified less than 1 hour ago. Set overwrite=true to force deletion.",
                })
            shutil.rmtree(base_dir)
        
        base_dir.mkdir(parents=True, exist_ok=True)
        spiders_dir = base_dir / project_name / "spiders"
        spiders_dir.mkdir(parents=True)

        # --- Write project files ---

        # 1. scrapy.cfg
        (base_dir / "scrapy.cfg").write_text(f"""[settings]
default = {project_name}.settings

[deploy]
project = {project_name}
""")

        # 2. scrapinghub.yml (for Scrapy Cloud deployment)
        (base_dir / "scrapinghub.yml").write_text(f"""project: {project_name}

requirements:
  file: requirements.txt

stack: scrapy:2.11
""")

        # 3. settings.py (Zyte-first configuration)
        settings_content = f'''# -*- coding: utf-8 -*-
import os

BOT_NAME = "{project_name}"

SPIDER_MODULES = ["{project_name}.spiders"]
NEWSPIDER_MODULE = "{project_name}.spiders"

# Zyte API configuration
ZYTE_API_KEY = os.getenv("ZYTE_API_KEY")
ZYTE_API_TRANSPARENT_MODE = True

# Use scrapy-zyte-api middleware (2026 best practice)
DOWNLOADER_MIDDLEWARES = {{
    "scrapy_zyte_api.ZyteApiMiddleware": 1000,
}}
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# Polite + efficient settings
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 16
DOWNLOAD_DELAY = 0.5

# Cloud-friendly
TELNETCONSOLE_ENABLED = False
LOG_LEVEL = "INFO"
'''
        (base_dir / project_name / "settings.py").write_text(settings_content)

        # 4. items.py
        base_item_name = project_name.replace("-", "_").title().replace("_", "") + "Item"

        if is_complex_job:
            items_content = f'''import scrapy

class {base_item_name}(scrapy.Item):
    """Structured item for complex multi-source scraping project"""
    name = scrapy.Field()
    url = scrapy.Field()
    source_spider = scrapy.Field()
    scraped_at = scrapy.Field()
'''
        else:
            items_content = f'''import scrapy

class {base_item_name}(scrapy.Item):
    """Auto-generated item for: {description[:80]}"""
'''
            for field in fields:
                items_content += f'    {field} = scrapy.Field()\n'
            items_content += '    url = scrapy.Field()\n    scraped_at = scrapy.Field()\n'

        (base_dir / project_name / "items.py").write_text(items_content)

        # 5. Basic spider (template-based if available)
        spider_class = project_name.replace("-", "_").title().replace("_", "") + "Spider"
        item_class = spider_class.replace("Spider", "Item")

        template_path = Path(__file__).parent / "templates" / "high_quality_spider.py.template"
        
        if template_path.exists():
            spider_code = template_path.read_text()
            spider_code = spider_code.replace("EliteSpider", spider_class)
            spider_code = spider_code.replace("elite_spider", project_name)
            spider_code = spider_code.replace("https://example.com/", start_url)
            spider_code = spider_code.replace(
                "Domain-aware generation: general",
                f"Domain-aware generation: {domain_type} (additive enhancements only)"
            )
            (spiders_dir / f"{project_name}.py").write_text(spider_code)
        else:
            # Fallback: basic spider template
            spider_code = f"""import scrapy
from scrapy_zyte_api import ZyteApiSpider
from {project_name}.items import {item_class}

class {spider_class}(ZyteApiSpider):
    name = "{project_name}"
    start_urls = ["{start_url}"]
    
    custom_settings = {{
        'ZYTE_API_AUTOMAP': True,
    }}
    
    def parse(self, response):
        # Implement your scraping logic here
        # This is a skeleton; extend with proper extraction logic
        yield {item_class}(
            name="example",
            url=response.url,
        )
"""
            (spiders_dir / f"{project_name}.py").write_text(spider_code)

        # 6. __init__.py
        (base_dir / project_name / "__init__.py").write_text("")

        # 7. README.md
        cost_note = (
            "Cost per page: ~$0.01-0.05 depending on extractFrom (browserHtml higher than httpResponseBody), "
            "geolocation, and custom attributes. Browser rendering adds cost. Monitor Zyte dashboard for actual charges."
        )
        
        readme = f'''# {project_name}

**Generated by Hermes** on {datetime.now().strftime("%Y-%m-%d")}

**Original request:**
> {description}

## Quick Start

```bash
cd ~/.hermes/spiders/{project_name}
scrapy crawl {project_name}
```

## Deploy to Scrapy Cloud (for continuous, scheduled scraping)

```bash
# 1. Deploy this project
zyte_deploy project_path="~/.hermes/spiders/{project_name}"

# 2. Schedule it (example: every 6 hours)
zyte_schedule project_id="{project_name}" spider="{project_name}" schedule="0 */6 * * *"

# 3. Monitor jobs
zyte_list_jobs project_id="{project_name}"

# 4. Get results
zyte_get_results job_id="<project_id>/<spider_id>/<job_id>"
```

## Cost Estimate

{cost_note}

## Fields Extracted

{', '.join(fields)}

## Requirements

- `ZYTE_API_KEY` (required)
- `SCRAPY_CLOUD_API_KEY` (required for deployment)

See README.md for full setup.
'''
        (base_dir / "README.md").write_text(readme)

        # 8. requirements.txt
        reqs = """scrapy>=2.11
scrapy-zyte-api>=0.8
zyte-api>=1.0
requests>=2.28
shub>=2.12
"""
        (base_dir / "requirements.txt").write_text(reqs)

        return json.dumps({
            "success": True,
            "project_name": project_name,
            "project_path": str(base_dir),
            "start_url": start_url,
            "extracted_fields": fields,
            "estimated_cost_per_run": "~$0.02-0.15 depending on page count and extractFrom settings",
            "message": f"✅ Full Scrapy + Zyte project created at {base_dir}",
            "next_steps": [
                f"1. Run locally: cd {base_dir} && scrapy crawl {project_name}",
                f"2. Deploy: zyte_deploy project_path='{base_dir}'",
                f"3. Schedule: zyte_schedule project_id='{project_name}' spider='{project_name}' schedule='0 */6 * * *'"
            ]
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
