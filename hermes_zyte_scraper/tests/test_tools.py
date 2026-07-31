"""Unit tests for hermes-zyte-scraper handlers."""

import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
helpers = _load_module("hzs_helpers", "zyte_helpers.py")


class TestZyteExtract(unittest.TestCase):
    def test_missing_url_returns_json_error(self):
        result = json.loads(tools.zyte_extract({}))
        self.assertFalse(result["success"])
        self.assertIn("url", result["error"])


class TestSchemaInference(unittest.TestCase):
    def test_indeed_uses_job_schema(self):
        schema = helpers.infer_schema(
            "https://www.indeed.com/jobs?q=engineer&l=Seattle",
            schema="auto",
            auto_schema=True,
        )
        self.assertEqual(schema, "jobPostingNavigation")

    def test_zillow_uses_product_list(self):
        schema = helpers.infer_schema(
            "https://www.zillow.com/homes/for_sale/Seattle-WA/",
            schema="auto",
            auto_schema=True,
        )
        self.assertEqual(schema, "productList")

    def test_manual_schema_override(self):
        schema = helpers.infer_schema(
            "https://www.indeed.com/jobs",
            schema="pageContent",
            auto_schema=False,
        )
        self.assertEqual(schema, "pageContent")


class TestPaginationHelpers(unittest.TestCase):
    def test_finds_books_next_page(self):
        html = '<li class="next"><a href="catalogue/page-2.html">next</a></li>'
        resp = {"browserHtml": html}
        next_url = tools._find_next_page_in_response(resp, "https://books.toscrape.com/")
        self.assertEqual(next_url, "catalogue/page-2.html")

    def test_skips_backward_page_links(self):
        html = (
            '<a href="catalogue/page-1.html">prev</a>'
            '<a href="catalogue/page-2.html">next</a>'
        )
        resp = {"browserHtml": html}
        next_url = tools._find_next_page_in_response(
            resp, "https://books.toscrape.com/catalogue/page-2.html"
        )
        self.assertIsNone(next_url)


class TestZyteBuildSpider(unittest.TestCase):
    def test_missing_start_url_returns_json_error(self):
        result = json.loads(
            tools.zyte_build_spider({"description": "scrape example listings"})
        )
        self.assertFalse(result["success"])
        self.assertIn("start_url", result["error"])

    def test_creates_project_with_spiders_init(self):
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
                self.assertTrue((project_path / "example-products/spiders/__init__.py").exists())


class TestOperations(unittest.TestCase):
    def test_deploy_dry_run(self):
        os.environ["SCRAPY_CLOUD_API_KEY"] = "test-key"
        client = operations.ScrapyCloudClient(dry_run=True)
        result = client.deploy(str(PLUGIN_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("DRY-RUN", result["stdout"])

    def test_schedule_uses_run_json(self):
        os.environ["SCRAPY_CLOUD_API_KEY"] = "test-key"
        client = operations.ScrapyCloudClient(dry_run=True)
        with patch.object(client, "_request") as mock_req:
            mock_req.return_value = MagicMock(
                status_code=200,
                json=lambda: {"status": "ok", "jobid": "867424/1/5"},
            )
            result = client.schedule("867424", "zillowseattle", tags=["test"])
            mock_req.assert_called_once()
            args, kwargs = mock_req.call_args
            self.assertEqual(args[2], "/run.json")
            self.assertEqual(kwargs["data"]["project"], "867424")
            self.assertEqual(kwargs["data"]["spider"], "zillowseattle")
            self.assertEqual(result["jobid"], "867424/1/5")

    def test_list_jobs_uses_jobs_list_json(self):
        os.environ["SCRAPY_CLOUD_API_KEY"] = "test-key"
        client = operations.ScrapyCloudClient(dry_run=True)
        with patch.object(client, "_request") as mock_req:
            mock_req.return_value = MagicMock(
                status_code=200,
                json=lambda: {"status": "ok", "jobs": [{"id": "867424/1/1"}], "count": 1},
            )
            jobs = client.list_jobs("867424", spider="zillowseattle")
            mock_req.assert_called_once()
            self.assertEqual(mock_req.call_args[0][2], "/jobs/list.json")
            self.assertEqual(len(jobs), 1)

    def test_get_results_maps_jsonlines_to_jl(self):
        os.environ["SCRAPY_CLOUD_API_KEY"] = "test-key"
        client = operations.ScrapyCloudClient(dry_run=True)
        with patch.object(client, "_request") as mock_req:
            mock_req.return_value = MagicMock(
                status_code=200,
                text='{"zpid":"1"}\n{"zpid":"2"}\n',
            )
            items = client.get_results("867424/1/3", fmt="jsonlines")
            self.assertEqual(mock_req.call_args[1]["params"]["format"], "jl")
            self.assertEqual(len(items), 2)


class TestSchemas(unittest.TestCase):
    def test_build_spider_requires_start_url(self):
        required = schemas.ZYTE_BUILD_SPIDER["parameters"]["required"]
        self.assertIn("start_url", required)
        self.assertIn("description", required)

    def test_extract_supports_session_and_custom_attributes(self):
        props = schemas.ZYTE_EXTRACT["parameters"]["properties"]
        self.assertIn("session_id", props)
        self.assertIn("custom_attributes", props)
        self.assertIn("auto_schema", props)

    def test_deploy_supports_dry_run(self):
        props = schemas.ZYTE_DEPLOY["parameters"]["properties"]
        self.assertIn("dry_run", props)


class TestPluginHooks(unittest.TestCase):
    def test_pre_llm_call_injects_context(self):
        hints = ("scrape", "spider", "zyte", "crawl", "extract", "scrapy cloud")
        text = "please scrape zillow listings"
        self.assertTrue(any(hint in text for hint in hints))


if __name__ == "__main__":
    unittest.main(verbosity=2)