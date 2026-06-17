"""Tool handlers for Zyte extraction and spider generation."""

import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter
from zyte_api import RequestError
from zyte_api import ZyteAPI


def _is_retryable_zyte_error(exc: BaseException) -> bool:
    if isinstance(exc, RequestError):
        status = getattr(exc, "status", None)
        if status in (429, 520, 500, 502, 503, 504):
            return True
    message = str(exc).lower()
    return any(token in message for token in ("429", "520", "rate limit", "timeout"))


@retry(
    retry=retry_if_exception(_is_retryable_zyte_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    reraise=True,
)
def _zyte_get(client: ZyteAPI, payload: dict) -> dict:
    return client.get(payload, endpoint="extract")


def _find_next_page_in_response(resp: dict, current_url: str) -> str | None:
    next_info = resp.get("nextPage") or {}
    if isinstance(next_info, dict) and next_info.get("url"):
        return next_info["url"]

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
                from urllib.parse import urljoin

                return urljoin(current_url, candidate)
            return candidate
    return None


def _extract_items_from_html(html: str) -> list:
    items = []
    patterns = [
        r'href=["\'](/[^"\']+/[a-z0-9-]{5,}[^"\']*)["\']',
        r'href=["\'](/[^"\']*detail[^"\']*)["\']',
        r'href=["\'](/[^"\']*item[^"\']*)["\']',
        r'href=["\'](/[^"\']*product[^"\']*)["\']',
    ]
    all_links = []
    for pat in patterns:
        all_links.extend(re.findall(pat, html, re.IGNORECASE))

    seen = set()
    for link in all_links:
        if link not in seen and len(link) > 6:
            seen.add(link)
            items.append({"url": link, "name": "General-purpose HTML fallback"})
            if len(items) >= 25:
                break
    return items


def zyte_extract(args: dict, **kwargs) -> str:
    url = args.get("url")
    max_pages = int(args.get("max_pages", 5))
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
            resp1: dict = {}
            items: list = []

            try:
                payload1 = {
                    "url": current_url,
                    schema: True,
                    "extractFrom": extract_from,
                }
                if args.get("geolocation"):
                    payload1["geolocation"] = args["geolocation"]

                resp1 = _zyte_get(client, payload1)
                auto_data = resp1.get(schema, {})
                if isinstance(auto_data, dict):
                    items = auto_data.get("products", auto_data.get("items", []))
                else:
                    items = auto_data if isinstance(auto_data, list) else []

                total_cost_estimate += 0.01
                page_result["extraction_method"] = f"auto-extract ({schema})"
            except Exception as exc:
                page_result["extraction_error"] = str(exc)

            if len(items) < 3:
                try:
                    payload2 = {"url": current_url, "browserHtml": True}
                    if args.get("geolocation"):
                        payload2["geolocation"] = args["geolocation"]

                    resp2 = _zyte_get(client, payload2)
                    fallback_items = _extract_items_from_html(resp2.get("browserHtml", ""))
                    if fallback_items:
                        items = fallback_items
                        page_result["extraction_method"] = "browserHtml + custom HTML parsing"
                        total_cost_estimate += 0.01
                except Exception as exc:
                    page_result["fallback_error"] = str(exc)

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

            next_url = _find_next_page_in_response(resp1, current_url)
            if next_url:
                current_url = next_url
            elif "page=" in current_url:
                current_url = re.sub(
                    r"page=(\d+)",
                    lambda match: f"page={int(match.group(1)) + 1}",
                    current_url,
                )
            else:
                current_url = None

            page += 1

        avg_items = sum(r["item_count"] for r in results) / max(len(results), 1)
        quality_score = min(1.0, avg_items / 15.0)
        recommendations = []
        if quality_score < 0.4:
            recommendations.append(
                "Extraction was weak on this site. Use zyte_build_spider to generate "
                "a custom spider, then deploy to Scrapy Cloud for larger runs."
            )
        if results and results[-1]["item_count"] == 0:
            recommendations.append(
                "Last page returned zero items — pagination likely ended or site structure changed."
            )

        return json.dumps(
            {
                "success": True,
                "pages_scraped": len(results),
                "total_items": sum(r["item_count"] for r in results),
                "quality_score": round(quality_score, 2),
                "cost_estimate": (
                    f"~${round(total_cost_estimate, 3)} "
                    "(Zyte charges only for successful responses)"
                ),
                "extract_from_used": extract_from,
                "recommendations": recommendations,
                "results": results,
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    text = re.sub(r"[\s-]+", "-", text)
    return text[:60] or "custom-spider"


def _extract_fields(description: str) -> list[str]:
    common = [
        "name",
        "price",
        "url",
        "rating",
        "availability",
        "asin",
        "address",
        "beds",
        "baths",
        "sqft",
        "title",
        "description",
        "image",
        "reviews",
        "category",
    ]
    found = [field for field in common if field in description.lower()]
    return found or ["name", "price", "url"]


def zyte_build_spider(args: dict, **kwargs) -> str:
    description = args.get("description", "")
    start_url = args.get("start_url", "")
    custom_name = args.get("spider_name", "")
    overwrite = bool(args.get("overwrite", False))

    if not description:
        return json.dumps({"success": False, "error": "description is required"})
    if not start_url:
        return json.dumps(
            {
                "success": False,
                "error": (
                    "start_url is required. Example: "
                    "'https://example.com/products' or "
                    "'https://www.zillow.com/homes/for_sale/'"
                ),
            }
        )

    try:
        project_name = _slugify(custom_name or description)
        fields = _extract_fields(description)

        domain_type = "general"
        if any(x in description.lower() for x in ["real estate", "zillow", "homes", "property"]):
            domain_type = "real_estate"
        elif any(x in description.lower() for x in ["amazon", "product", "e-commerce", "shop"]):
            domain_type = "ecommerce"
        elif any(x in description.lower() for x in ["job", "indeed", "career"]):
            domain_type = "jobs"

        is_complex_job = len(description) > 160 or any(
            kw in description.lower()
            for kw in [
                "multiple sources",
                "several sites",
                "different websites",
                "multi-source",
                "various platforms",
            ]
        )

        base_dir = Path.home() / ".hermes" / "spiders" / project_name
        if base_dir.exists():
            if not overwrite:
                return json.dumps(
                    {
                        "success": False,
                        "error": (
                            f"Project directory already exists at {base_dir}. "
                            "Set overwrite=true to regenerate."
                        ),
                    }
                )
            shutil.rmtree(base_dir)

        base_dir.mkdir(parents=True, exist_ok=True)
        spiders_dir = base_dir / project_name / "spiders"
        spiders_dir.mkdir(parents=True)

        (base_dir / "scrapy.cfg").write_text(
            f"[settings]\ndefault = {project_name}.settings\n\n[deploy]\nproject = {project_name}\n"
        )
        (base_dir / "scrapinghub.yml").write_text(
            f"project: {project_name}\n\nrequirements:\n  file: requirements.txt\n\nstack: scrapy:2.11\n"
        )

        settings_content = f'''# -*- coding: utf-8 -*-
import os

BOT_NAME = "{project_name}"

SPIDER_MODULES = ["{project_name}.spiders"]
NEWSPIDER_MODULE = "{project_name}.spiders"

ZYTE_API_KEY = os.getenv("ZYTE_API_KEY")
ZYTE_API_TRANSPARENT_MODE = True

DOWNLOADER_MIDDLEWARES = {{
    "scrapy_zyte_api.ZyteApiMiddleware": 1000,
}}
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 16
DOWNLOAD_DELAY = 0.5
TELNETCONSOLE_ENABLED = False
LOG_LEVEL = "INFO"
'''
        (base_dir / project_name / "settings.py").write_text(settings_content)

        base_item_name = project_name.replace("-", "_").title().replace("_", "") + "Item"
        if is_complex_job:
            items_content = f'''import scrapy

class {base_item_name}(scrapy.Item):
    name = scrapy.Field()
    url = scrapy.Field()
    source_spider = scrapy.Field()
    scraped_at = scrapy.Field()
'''
        else:
            items_content = (
                f'import scrapy\n\nclass {base_item_name}(scrapy.Item):\n'
                f'    """Auto-generated item for: {description[:80]}"""\n'
            )
            for field in fields:
                items_content += f"    {field} = scrapy.Field()\n"
            items_content += "    url = scrapy.Field()\n    scraped_at = scrapy.Field()\n"

        (base_dir / project_name / "items.py").write_text(items_content)

        spider_class = project_name.replace("-", "_").title().replace("_", "") + "Spider"
        item_class = spider_class.replace("Spider", "Item")
        template_path = Path(__file__).parent / "templates" / "high_quality_spider.py.template"

        if template_path.exists():
            spider_code = template_path.read_text()
            spider_code = spider_code.replace("EliteSpider", spider_class)
            spider_code = spider_code.replace("elite_spider", project_name)
            spider_code = spider_code.replace("https://example.com/", start_url)
            spider_code = spider_code.replace(
                "example.com",
                start_url.split("/")[2] if "://" in start_url else "example.com",
            )
            spider_code = spider_code.replace(
                "Domain-aware generation: general",
                f"Domain-aware generation: {domain_type} (additive enhancements only)",
            )
            (spiders_dir / f"{project_name}.py").write_text(spider_code)
        else:
            (spiders_dir / f"{project_name}.py").write_text(
                f'''import scrapy
from scrapy_zyte_api import ZyteApiSpider
from {project_name}.items import {item_class}

class {spider_class}(ZyteApiSpider):
    name = "{project_name}"
    start_urls = ["{start_url}"]
'''
            )

        (base_dir / project_name / "__init__.py").write_text("")

        cost_note = (
            "Cost per page: ~$0.01-0.05 depending on extractFrom and browser rendering. "
            "Monitor your Zyte dashboard and set spending limits."
        )
        readme = f'''# {project_name}

Generated by Hermes on {datetime.now().strftime("%Y-%m-%d")}

> {description}

## Local run

```bash
cd ~/.hermes/spiders/{project_name}
pip install -r requirements.txt
scrapy crawl {project_name}
```

## Scrapy Cloud

```bash
zyte_deploy project_path="~/.hermes/spiders/{project_name}"
zyte_schedule project_id="{project_name}" spider="{project_name}"
zyte_list_jobs project_id="{project_name}"
zyte_get_results job_id="<project>/<spider>/<job>"
```

{cost_note}

Fields: {", ".join(fields)}
'''
        (base_dir / "README.md").write_text(readme)
        (base_dir / "requirements.txt").write_text(
            "scrapy>=2.11\nscrapy-zyte-api>=0.8\nzyte-api>=1.0\nrequests>=2.28\nshub>=2.12\n"
        )

        return json.dumps(
            {
                "success": True,
                "project_name": project_name,
                "project_path": str(base_dir),
                "start_url": start_url,
                "extracted_fields": fields,
                "estimated_cost_per_run": "~$0.02-0.15 depending on page count and extractFrom",
                "message": f"Scrapy + Zyte project created at {base_dir}",
                "next_steps": [
                    f"Run locally: cd {base_dir} && scrapy crawl {project_name}",
                    f"Deploy: zyte_deploy project_path='{base_dir}'",
                    (
                        f"Schedule: zyte_schedule project_id='{project_name}' "
                        f"spider='{project_name}'"
                    ),
                ],
            }
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})
