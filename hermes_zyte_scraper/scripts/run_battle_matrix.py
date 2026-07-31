#!/usr/bin/env python3
"""Run live battle matrix and validate against expected minimums."""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from tools import zyte_extract  # noqa: E402

TESTS = [
    {"name": "books.toscrape.com", "args": {"url": "https://books.toscrape.com/", "max_pages": 5}},
    {
        "name": "indeed_jobs_seattle",
        "args": {
            "url": "https://www.indeed.com/jobs?q=software+engineer&l=Seattle%2C+WA",
            "max_pages": 2,
        },
    },
    {
        "name": "zillow_seattle",
        "args": {"url": "https://www.zillow.com/homes/for_sale/Seattle-WA/", "max_pages": 3},
    },
    {"name": "amazon_search", "args": {"url": "https://www.amazon.com/s?k=laptop", "max_pages": 2}},
]

EXPECTED_PATH = PLUGIN_ROOT / "tests/fixtures/battle_matrix_expected.json"


def main() -> int:
    expected = json.loads(EXPECTED_PATH.read_text())
    minimums = expected["minimum_pass"]
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "tests": [], "passed": True}

    for test in TESTS:
        name = test["name"]
        print(f"Running {name}...", flush=True)
        start = time.time()
        result = json.loads(zyte_extract(test["args"]))
        elapsed = round(time.time() - start, 1)
        entry = {
            "name": name,
            "elapsed_s": elapsed,
            "pages_scraped": result.get("pages_scraped"),
            "total_items": result.get("total_items"),
            "quality_score": result.get("quality_score"),
            "schema_used": result.get("schema_used"),
            "success": result.get("success"),
        }
        report["tests"].append(entry)

        if not result.get("success"):
            print(f"  FAIL: {result.get('error')}")
            report["passed"] = False
            continue

        floor = minimums.get(name, {})
        ok = True
        if entry["pages_scraped"] < floor.get("pages_scraped_min", 1):
            ok = False
        if entry["total_items"] < floor.get("total_items_min", 1):
            ok = False
        if entry["quality_score"] < floor.get("quality_min", 0):
            ok = False
        status = "PASS" if ok else "FAIL"
        print(
            f"  {status}: pages={entry['pages_scraped']} items={entry['total_items']} "
            f"quality={entry['quality_score']} schema={entry['schema_used']} ({elapsed}s)"
        )
        if not ok:
            report["passed"] = False

    out = PLUGIN_ROOT / "battle_matrix_latest.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {out}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())