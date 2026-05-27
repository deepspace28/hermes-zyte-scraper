"""
Production-grade operational layer for managing spiders on Scrapy Cloud.

This module provides a clean, reusable client for the operational tools
(zyte_deploy, zyte_schedule, zyte_list_jobs, zyte_get_results).

Goal: Make the plugin reliable enough for real production use.
"""

import os
import json
import requests
from typing import Any, Dict, List, Optional
from pathlib import Path


class ScrapyCloudError(Exception):
    """Base exception for Scrapy Cloud operational errors."""
    pass


class ScrapyCloudClient:
    """
    A production-oriented client for Scrapy Cloud operations.

    Handles authentication, error handling, name resolution, and provides
    a cleaner interface than raw API calls.
    """

    # Per 2026 Scrapy Cloud reference:
    # - Jobs/schedules/run on app.zyte.com
    # - Items, logs, etc. primarily on storage.zyte.com
    # We keep a flexible client and route appropriately.
    JOBS_BASE = "https://app.zyte.com/api"
    STORAGE_BASE = "https://storage.zyte.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SCRAPY_CLOUD_API_KEY")
        if not self.api_key:
            raise ScrapyCloudError(
                "SCRAPY_CLOUD_API_KEY is not set. "
                "Please set it in ~/.hermes/.env or pass it explicitly."
            )
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _request(self, method: str, base: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{base}{endpoint}"
        try:
            resp = self.session.request(method, url, timeout=60, **kwargs)
            if resp.status_code >= 400:
                raise ScrapyCloudError(
                    f"Scrapy Cloud API error {resp.status_code}: {resp.text}"
                )
            return resp
        except requests.RequestException as e:
            raise ScrapyCloudError(f"Network error talking to Scrapy Cloud: {e}")

    def resolve_project(self, name_or_id: str) -> str:
        """Accepts project name or ID and returns the numeric project ID (via Jobs API)."""
        if name_or_id.isdigit():
            return name_or_id

        resp = self._request("GET", self.JOBS_BASE, "/projects", params={"name": name_or_id})
        data = resp.json()
        projects = data.get("projects", [])
        if not projects:
            raise ScrapyCloudError(f"Could not find project named '{name_or_id}'")
        return str(projects[0]["id"])

    def deploy(self, project_path: str, project_name: Optional[str] = None) -> Dict[str, Any]:
        """Deploy a local Scrapy project to Scrapy Cloud."""
        path = Path(project_path).expanduser().resolve()
        if not path.exists():
            raise ScrapyCloudError(f"Project path does not exist: {path}")

        name = project_name or path.name

        # Ensure scrapinghub.yml exists
        shub_yml = path / "scrapinghub.yml"
        if not shub_yml.exists():
            shub_yml.write_text(f"""project: {name}

requirements:
  file: requirements.txt

stack: scrapy:2.11
""")

        # Run shub deploy
        import subprocess
        result = subprocess.run(
            ["shub", "deploy"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=180
        )

        if result.returncode != 0:
            raise ScrapyCloudError(
                f"shub deploy failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )

        return {
            "success": True,
            "project_name": name,
            "stdout": result.stdout.strip(),
        }

    def schedule(
        self,
        project_id: str,
        spider: str,
        schedule: Optional[str] = None,
        units: int = 1,
        tags: Optional[list] = None,
        job_settings: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """Schedule a spider (one-time or recurring). Follows Scrapy Cloud Jobs API (app.zyte.com)."""
        project_id = self.resolve_project(project_id)

        payload = {"spider": spider, "units": units}
        if tags:
            for t in tags:
                payload.setdefault("add_tag", [])
                payload["add_tag"].append(t) if isinstance(payload.get("add_tag"), list) else payload.update({"add_tag": [t]})
        if job_settings:
            payload["job_settings"] = job_settings

        if schedule:
            payload["cron"] = schedule
            endpoint = f"/projects/{project_id}/schedules"
            base = self.JOBS_BASE
        else:
            endpoint = f"/projects/{project_id}/jobs"
            base = self.JOBS_BASE

        resp = self._request("POST", base, endpoint, json=payload)
        return resp.json()

    def list_jobs(
        self,
        project_id: str,
        spider: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 20,
        tags: Optional[list] = None,
    ) -> List[Dict[str, Any]]:
        """List jobs for a project. Uses app.zyte.com Jobs API with name support and tag filters."""
        project_id = self.resolve_project(project_id)
        params = {"count": limit}
        if spider:
            params["spider"] = spider
        if state and state != "all":
            params["state"] = state
        if tags:
            params["has_tag"] = ",".join(tags) if isinstance(tags, list) else tags

        resp = self._request("GET", self.JOBS_BASE, f"/projects/{project_id}/jobs", params=params)
        return resp.json().get("jobs", [])

    def get_results(
        self,
        job_id: str,
        fmt: str = "jsonlines",
        limit: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch items from a job. Uses storage.zyte.com Items API with better pagination awareness."""
        params = {"format": fmt}
        if limit > 0:
            params["count"] = limit

        resp = self._request("GET", self.STORAGE_BASE, f"/items/{job_id}", params=params)

        if fmt in ("jsonlines", "jl"):
            lines = [line for line in resp.text.strip().split("\n") if line]
            items = [json.loads(line) for line in lines]
            return items[:limit] if limit > 0 else items
        else:
            data = resp.json()
            items = data.get("items", data) if isinstance(data, dict) else data
            return items[:limit] if limit > 0 and isinstance(items, list) else items


# Convenience functions that match the tool interface
def zyte_deploy(args: dict, **kwargs) -> str:
    client = ScrapyCloudClient()
    try:
        result = client.deploy(
            project_path=args["project_path"],
            project_name=args.get("project_name"),
        )
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def zyte_schedule(args: dict, **kwargs) -> str:
    client = ScrapyCloudClient()
    try:
        result = client.schedule(
            project_id=args["project_id"],
            spider=args["spider"],
            schedule=args.get("schedule"),
            units=args.get("units", 1),
            tags=args.get("tags"),
            job_settings=args.get("job_settings"),
        )
        return json.dumps({"success": True, "data": result})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def zyte_list_jobs(args: dict, **kwargs) -> str:
    client = ScrapyCloudClient()
    try:
        jobs = client.list_jobs(
            project_id=args["project_id"],
            spider=args.get("spider"),
            state=args.get("state"),
            limit=args.get("limit", 20),
            tags=args.get("tags"),
        )
        return json.dumps({"success": True, "jobs": jobs})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def zyte_get_results(args: dict, **kwargs) -> str:
    client = ScrapyCloudClient()
    try:
        items = client.get_results(
            job_id=args["job_id"],
            fmt=args.get("format", "jsonlines"),
            limit=args.get("limit", 0),
        )
        return json.dumps({"success": True, "items": items})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
