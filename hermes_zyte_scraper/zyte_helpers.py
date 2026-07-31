"""Shared Zyte extraction helpers: schema inference, item parsing, HTML fallbacks."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse


SCHEMA_ITEM_KEYS: dict[str, list[str]] = {
    "productList": ["products", "items"],
    "productNavigation": ["products", "items"],
    "jobPostingNavigation": ["jobPostings", "items"],
    "articleList": ["articles", "items"],
    "articleNavigation": ["articles", "items"],
    "pageContent": ["items"],
}


def infer_schema(url: str | None, schema: str | None = None, auto_schema: bool = True) -> str:
    """Pick the best Zyte auto-extract schema for a URL (Zyte: one schema per request)."""
    if not url:
        return schema if schema and schema not in ("", "auto") else "productList"
    if schema and schema not in ("", "auto") and not auto_schema:
        return schema

    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()

    if "indeed.com" in host or any(x in path for x in ("/jobs", "/job/", "/careers")):
        return "jobPostingNavigation"
    if any(x in host for x in ("zillow.com", "redfin.com", "realtor.com", "trulia.com")):
        return "productList"
    if any(x in host for x in ("amazon.", "ebay.", "etsy.", "walmart.", "target.")):
        return "productList"
    if any(x in host for x in ("news.", "medium.com", "substack.com")) or "/article" in path:
        return "articleList"
    if "quotes.toscrape.com" in host:
        return "pageContent"

    if schema and schema not in ("", "auto"):
        return schema
    return "productList"


def parse_auto_extract_items(schema: str, auto_data: dict | list | None) -> list:
    """Normalize Zyte auto-extract response into a flat item list."""
    if auto_data is None:
        return []
    if isinstance(auto_data, list):
        return auto_data
    if not isinstance(auto_data, dict):
        return []

    for key in SCHEMA_ITEM_KEYS.get(schema, ["items", "products", "articles", "jobPostings"]):
        value = auto_data.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def build_custom_attributes_payload(fields: list[str] | str | None) -> dict | None:
    """Build Zyte customAttributes schema from a field list or JSON schema string."""
    if not fields:
        return None
    if isinstance(fields, str):
        fields = fields.strip()
        if fields.startswith("{"):
            try:
                return json.loads(fields)
            except json.JSONDecodeError:
                pass
        field_list = [f.strip() for f in fields.split(",") if f.strip()]
    else:
        field_list = list(fields)

    if not field_list:
        return None

    properties = {name: {"type": "string", "description": name} for name in field_list}
    return {
        "type": "object",
        "properties": properties,
        "required": field_list[: min(3, len(field_list))],
    }


def parse_zillow_listings_from_html(html: str) -> list[dict]:
    """Extract Zillow listing cards from embedded JSON / HTML patterns."""
    items: list[dict] = []
    seen: set[str] = set()

    json_blobs = re.findall(
        r'\{[^{}]*"zpid"\s*:\s*"?(\d+)"?[^{}]*"price"\s*:\s*"?([^",}]*)"?[^{}]*\}',
        html,
    )
    for zpid, price in json_blobs:
        if zpid in seen:
            continue
        seen.add(zpid)
        items.append(
            {
                "zpid": zpid,
                "url": f"https://www.zillow.com/homedetails/{zpid}_zpid/",
                "price": price,
                "name": f"Listing {zpid}",
            }
        )

    for match in re.finditer(
        r'href="([^"]*/homedetails/[^"]+_zpid/)"[^>]*>.*?'
        r'(?:\$[\d,]+|<span[^>]*>[\d,]+</span>)',
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        url = match.group(1).replace("\\/", "/")
        zpid_match = re.search(r"/(\d+)_zpid/", url)
        if not zpid_match:
            continue
        zpid = zpid_match.group(1)
        if zpid in seen:
            continue
        seen.add(zpid)
        chunk = match.group(0)
        price_match = re.search(r"\$[\d,]+", chunk)
        beds_match = re.search(r"(\d+)\s*bd", chunk, re.I)
        baths_match = re.search(r"(\d+)\s*ba", chunk, re.I)
        sqft_match = re.search(r"([\d,]+)\s*sqft", chunk, re.I)
        items.append(
            {
                "zpid": zpid,
                "url": url,
                "price": price_match.group(0).replace("$", "").replace(",", "") if price_match else None,
                "beds": beds_match.group(1) if beds_match else None,
                "baths": baths_match.group(1) if baths_match else None,
                "sqft": sqft_match.group(1).replace(",", "") if sqft_match else None,
                "name": f"Listing {zpid}",
            }
        )

    for match in re.finditer(r'href="([^"]*/homedetails/[^"]+_zpid/)"', html, re.I):
        url = match.group(1).replace("\\/", "/")
        zpid_match = re.search(r"/(\d+)_zpid/", url)
        if not zpid_match:
            continue
        zpid = zpid_match.group(1)
        if zpid in seen:
            continue
        seen.add(zpid)
        items.append({"zpid": zpid, "url": url, "name": f"Listing {zpid}"})

    return items


def extract_items_from_html(html: str, url: str = "") -> list[dict]:
    """Domain-aware HTML fallback when Zyte auto-extract returns few items."""
    host = urlparse(url).netloc.lower() if url else ""
    if "zillow.com" in host:
        zillow_items = parse_zillow_listings_from_html(html)
        if zillow_items:
            return zillow_items

    items: list[dict] = []
    patterns = [
        r'href=["\'](/[^"\']+/[a-z0-9-]{5,}[^"\']*)["\']',
        r'href=["\'](/[^"\']*detail[^"\']*)["\']',
        r'href=["\'](/[^"\']*item[^"\']*)["\']',
        r'href=["\'](/[^"\']*product[^"\']*)["\']',
    ]
    all_links: list[str] = []
    for pat in patterns:
        all_links.extend(re.findall(pat, html, re.IGNORECASE))

    seen: set[str] = set()
    for link in all_links:
        if link not in seen and len(link) > 6:
            if any(bad in link for bad in ("bootstrap", ".css", ".js", "login", "signup")):
                continue
            seen.add(link)
            items.append({"url": link, "name": "General-purpose HTML fallback"})
            if len(items) >= 25:
                break
    return items