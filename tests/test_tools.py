"""Unit tests for hermes-zyte-scraper handlers."""

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, filename: str):
    path = PLUGIN_ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tools = _load_module("hzs_tools", "tools.py")
schemas = _load_module("hzs_schemas", "schemas.py")
operations = _load_module("hzs_operations", "operations.py")


class TestZyteExtract(unittest.TestCase):
    def test_missing_url_returns_json_error(self):
        result = json.loads(tools.zyte_extract({}))
        self.assertFalse(result["success"])
        self.assertIn("url", result["error"])


class TestZyteBuildSpider(unittest.TestCase):
    def test_missing_start_url_returns_json_error(self):
        result = json.loads(
            tools.zyte_build_spider({"description": "scrape example listings"})
        )
        self.assertFalse(result["success"])
        self.assertIn("start_url", result["error"])

    def test_creates_project(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch.object(tools.Path, "home", return_value=tmp_path):
                result = json.loads(
                    tools.zyte_build_spider(
                        {
                            "description": "Extract product name and price from listings",
                            "start_url": "https://example.com/products",
                            "spider_name": "example-products",
                            "overwrite": True,
                        }
                    )
                )
                self.assertTrue(result["success"])
                project_path = Path(result["project_path"])
                self.assertTrue(project_path.exists())
                self.assertTrue((project_path / "scrapy.cfg").exists())
                self.assertTrue((project_path / "scrapinghub.yml").exists())
                self.assertTrue((project_path / "requirements.txt").exists())


class TestOperationsDryRun(unittest.TestCase):
    def test_deploy_dry_run(self):
        os.environ["SCRAPY_CLOUD_API_KEY"] = "test-key"
        client = operations.ScrapyCloudClient(dry_run=True)
        result = client.deploy(str(PLUGIN_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("DRY-RUN", result["stdout"])


class TestSchemas(unittest.TestCase):
    def test_build_spider_requires_start_url(self):
        required = schemas.ZYTE_BUILD_SPIDER["parameters"]["required"]
        self.assertIn("start_url", required)
        self.assertIn("description", required)

    def test_deploy_supports_dry_run(self):
        props = schemas.ZYTE_DEPLOY["parameters"]["properties"]
        self.assertIn("dry_run", props)

    def test_list_jobs_supports_offset(self):
        props = schemas.ZYTE_LIST_JOBS["parameters"]["properties"]
        self.assertIn("offset", props)


class TestPluginHooks(unittest.TestCase):
    def test_pre_llm_call_injects_context(self):
        hints = ("scrape", "spider", "zyte", "crawl", "extract", "scrapy cloud")
        text = "please scrape zillow listings"
        self.assertTrue(any(hint in text for hint in hints))


if __name__ == "__main__":
    unittest.main(verbosity=2)
